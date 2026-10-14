#!/usr/bin/env python3
"""HTTP server for POST /api/subscribe (WSGI-style, stdlib only)."""

from __future__ import annotations

import cgi
import io
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.subscribe_service import SubscribeInput, subscribe  # noqa: E402


def _client_ip(headers: dict[str, str]) -> str:
    forwarded = headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return headers.get("Remote-Addr", "127.0.0.1")


def _parse_body(content_type: str, body: bytes) -> dict[str, str]:
    if "application/json" in content_type:
        data = json.loads(body.decode("utf-8") or "{}")
        return {k: str(v) for k, v in data.items()}
    if "multipart/form-data" in content_type:
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": str(len(body)),
        }
        fs = cgi.FieldStorage(
            fp=io.BytesIO(body), environ=environ, keep_blank_values=True
        )
        out: dict[str, str] = {}
        for key in fs.keys():
            field = fs[key]
            if isinstance(field, list):
                out[key] = field[0].value if field else ""
            else:
                out[key] = field.value or ""
        return out
    # application/x-www-form-urlencoded
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {k: (v[0] if v else "") for k, v in parsed.items()}


def _redirect_for(lang: str, ok: bool) -> str:
    if lang == "en":
        return "/en/newsletter-thanks.html" if ok else "/en/newsletter-error.html"
    return "/newsletter-merci.html" if ok else "/newsletter-erreur.html"


class Handler(BaseHTTPRequestHandler):
    server_version = "THTSubscribe/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/subscribe":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        try:
            fields = _parse_body(ctype, body)
        except (json.JSONDecodeError, ValueError):
            fields = {}

        inp = SubscribeInput(
            name=fields.get("name", ""),
            email=fields.get("email", ""),
            city=fields.get("city", ""),
            organisation=fields.get("organisation", ""),
            consent=fields.get("consent", "") in ("1", "true", "on", "yes"),
            honeypot=fields.get("company_website", "") or fields.get("website", ""),
            lang=fields.get("lang", "fr"),
            client_ip=_client_ip(
                {
                    "X-Forwarded-For": self.headers.get("X-Forwarded-For", ""),
                    "Remote-Addr": self.client_address[0],
                }
            ),
        )

        test_mode = os.environ.get("SUBSCRIBE_TEST_MODE", "") == "1"
        result = subscribe(inp, test_mode=test_mode)

        wants_json = "application/json" in self.headers.get("Accept", "") or fields.get(
            "ajax", ""
        ) in ("1", "true")

        if wants_json:
            self.send_response(200 if result.ok else 400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {"ok": result.ok, "code": result.code, "message": result.message}
            self.wfile.write(json.dumps(payload).encode())
            return

        loc = _redirect_for(inp.lang, result.ok)
        self.send_response(303)
        self.send_header("Location", loc)
        self.end_headers()


def main() -> None:
    host = os.environ.get("SUBSCRIBE_BIND", "127.0.0.1")
    port = int(os.environ.get("SUBSCRIBE_PORT", "8000"))
    HTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
