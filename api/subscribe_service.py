"""Newsletter subscribe: Notion CRM + SMTP notification."""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

NOTION_VERSION = "2022-06-28"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# In-memory rate limit: IP -> list of timestamps
_RATE: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 3600
_RATE_MAX = 5


@dataclass
class SubscribeInput:
    name: str
    email: str
    city: str
    organisation: str
    consent: bool
    honeypot: str
    lang: str
    client_ip: str


@dataclass
class SubscribeResult:
    ok: bool
    code: str
    message: str
    duplicate: bool = False


class NotionClient:
    def __init__(self, token: str, database_id: str) -> None:
        self.token = token
        self.database_id = database_id.replace("-", "")
        if len(self.database_id) == 32:
            self.database_id = (
                f"{self.database_id[:8]}-{self.database_id[8:12]}-"
                f"{self.database_id[12:16]}-{self.database_id[16:20]}-{self.database_id[20:]}"
            )
        self._schema: dict[str, dict[str, Any]] | None = None

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"https://api.notion.com/v1{path}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def load_schema(self) -> dict[str, dict[str, Any]]:
        if self._schema is not None:
            return self._schema
        data = self._request("GET", f"/databases/{self.database_id}")
        self._schema = data.get("properties", {})
        return self._schema

    def find_by_email(self, email: str, email_prop: str) -> bool:
        body = {
            "filter": {"property": email_prop, "email": {"equals": email.lower()}},
            "page_size": 1,
        }
        data = self._request("POST", f"/databases/{self.database_id}/query", body)
        return len(data.get("results", [])) > 0

    def create_contact(self, props: dict[str, Any]) -> None:
        body = {"parent": {"database_id": self.database_id}, "properties": props}
        self._request("POST", "/pages", body)


def _title_prop(name: str) -> dict:
    return {"title": [{"text": {"content": name[:2000]}}]}


def _rich_text_prop(text: str) -> dict:
    if not text:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def _email_prop(email: str) -> dict:
    return {"email": email.lower()[:320]}


def _select_prop(option: str) -> dict:
    return {"select": {"name": option}}


def build_notion_properties(schema: dict[str, dict], inp: SubscribeInput) -> dict[str, Any]:
    """Map form fields to Notion properties; skip unknown select options."""
    props: dict[str, Any] = {}
    notes: list[str] = []

    def prop_by_type(types: tuple[str, ...]) -> str | None:
        for name, meta in schema.items():
            if meta.get("type") in types:
                return name
        return None

    title_name = prop_by_type(("title",))
    email_name = prop_by_type(("email",))
    if not title_name or not email_name:
        raise RuntimeError("Database missing title or email property")

    props[title_name] = _title_prop(inp.name.strip())
    props[email_name] = _email_prop(inp.email)

    for field, notion_names, value in (
        ("Country/City", ("Country/City", "City", "Country"), inp.city),
        ("Organisation", ("Organisation", "Organization"), inp.organisation),
    ):
        if not value.strip():
            continue
        key = next((n for n in notion_names if n in schema), None)
        if not key:
            continue
        ptype = schema[key]["type"]
        if ptype == "rich_text":
            props[key] = _rich_text_prop(value.strip())
        elif ptype == "text":
            props[key] = _rich_text_prop(value.strip())

    source_val = "Website newsletter form"
    if "Source" in schema and schema["Source"].get("type") == "select":
        options = {o["name"] for o in schema["Source"].get("select", {}).get("options", [])}
        if source_val in options:
            props["Source"] = _select_prop(source_val)
        else:
            notes.append(f"Source: {source_val}")
    elif "Source" in schema and schema["Source"].get("type") == "rich_text":
        props["Source"] = _rich_text_prop(source_val)

    rel_val = "Newsletter signup (website)"
    if "Relationship" in schema and schema["Relationship"].get("type") == "select":
        options = {o["name"] for o in schema["Relationship"].get("select", {}).get("options", [])}
        if rel_val in options:
            props["Relationship"] = _select_prop(rel_val)
        else:
            notes.append(f"Relationship: {rel_val}")
    elif "Relationship" in schema and schema["Relationship"].get("type") == "rich_text":
        props["Relationship"] = _rich_text_prop(rel_val)

    notes.append(f"Lang: {inp.lang}")
    if "Notes" in schema and schema["Notes"].get("type") == "rich_text":
        existing = notes
        props["Notes"] = _rich_text_prop("; ".join(existing))

    return props


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _RATE[ip] if now - t < _RATE_WINDOW]
    _RATE[ip] = hits
    if len(hits) >= _RATE_MAX:
        return False
    _RATE[ip].append(now)
    return True


def validate(inp: SubscribeInput) -> SubscribeResult | None:
    if inp.honeypot.strip():
        return SubscribeResult(True, "ok", "OK", duplicate=False)
    if not check_rate_limit(inp.client_ip or "unknown"):
        return SubscribeResult(False, "rate_limit", "Too many requests")
    if not inp.consent:
        return SubscribeResult(False, "consent", "Consent required")
    if not inp.name.strip() or len(inp.name.strip()) < 2:
        return SubscribeResult(False, "name", "Invalid name")
    if not EMAIL_RE.match(inp.email.strip()):
        return SubscribeResult(False, "email", "Invalid email")
    return None


def send_notify_email(inp: SubscribeInput, cfg: dict[str, str]) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[THT Newsletter] {inp.name.strip()}"
    msg["From"] = cfg["smtp_from"]
    msg["To"] = cfg["notify_to"]
    body = (
        f"New newsletter signup ({inp.lang})\n\n"
        f"Name: {inp.name.strip()}\n"
        f"Email: {inp.email.strip()}\n"
        f"City: {inp.city.strip() or '—'}\n"
        f"Organisation: {inp.organisation.strip() or '—'}\n"
    )
    msg.set_content(body)

    port = int(cfg.get("smtp_port", "465"))
    host = cfg["smtp_host"]
    user = cfg["smtp_user"]
    password = cfg["smtp_pass"]
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)


def subscribe(inp: SubscribeInput, *, test_mode: bool = False) -> SubscribeResult:
    if not test_mode:
        test_mode = os.environ.get("SUBSCRIBE_TEST_MODE", "") == "1"
    err = validate(inp)
    if err is not None:
        return err

    if test_mode:
        return SubscribeResult(True, "ok", "Test mode: stored", duplicate=False)

    token = os.environ.get("NOTION_TOKEN", "")
    db_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not token or not db_id:
        return SubscribeResult(False, "config", "Service not configured")

    notion = NotionClient(token, db_id)
    schema = notion.load_schema()
    email_prop = next(
        (n for n, m in schema.items() if m.get("type") == "email"),
        "Email",
    )
    if notion.find_by_email(inp.email.strip(), email_prop):
        return SubscribeResult(True, "ok", "Already subscribed", duplicate=True)

    props = build_notion_properties(schema, inp)
    notion.create_contact(props)

    smtp_required = os.environ.get("SMTP_HOST", "")
    if smtp_required:
        cfg = {
            "smtp_host": os.environ["SMTP_HOST"],
            "smtp_port": os.environ.get("SMTP_PORT", "465"),
            "smtp_user": os.environ.get("SMTP_USER", ""),
            "smtp_pass": os.environ.get("SMTP_PASS", ""),
            "smtp_from": os.environ.get("SMTP_FROM", ""),
            "notify_to": os.environ.get("NOTIFY_TO", "compagnie.tht@gmail.com"),
        }
        if cfg["smtp_from"] and cfg["smtp_user"]:
            send_notify_email(inp, cfg)

    return SubscribeResult(True, "ok", "Subscribed", duplicate=False)
