#!/usr/bin/env python3
"""Verify bundled pages render (styled) under Caddy."""
from __future__ import annotations

import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
PAGES = [
    "/",
    "/cherche-en-corps",
    "/fleur",
    "/windows",
    "/contact",
    "/en/",
    "/en/cherche-en-corps",
    "/en/fleur",
    "/en/windows",
    "/en/contact",
]


def check(page, path: str) -> list[str]:
    errors: list[str] = []
    console: list[str] = []

    BENIGN = (
        "No available adapters.",
        "Unrecognized feature: 'web-share'",
        "Permissions policy violation: compute-pressure",
    )

    def on_console(msg):
        if msg.type not in ("error", "warning"):
            return
        text = msg.text or ""
        if any(b in text for b in BENIGN):
            return
        console.append(text)

    page.on("console", on_console)
    page.goto(BASE + path, wait_until="load", timeout=120000)
    try:
        page.wait_for_selector("[data-screen-label]", timeout=90000)
    except Exception as e:
        errors.append(f"timeout data-screen-label: {e}")
    page.wait_for_timeout(2000)
    err = page.query_selector("#__bundler_err")
    if err and err.is_visible():
        errors.append(f"bundler_err: {err.inner_text()[:500]}")
    # Production uses min-width ~1100 on screen root
    root = page.locator("[data-screen-label]").first
    if root.count():
        w = root.evaluate("el => getComputedStyle(el).minWidth")
        if w in ("0px", "auto", ""):
            errors.append(f"minWidth suspicious: {w}")
    thumb = page.query_selector("#__bundler_thumbnail")
    if thumb:
        vis = thumb.evaluate("el => getComputedStyle(el).display")
        if vis != "none" and thumb.evaluate("el => el.offsetHeight") > 100:
            errors.append("thumbnail still visible (unpack failed?)")
    if console:
        errors.append("console: " + "; ".join(console[:5]))
    return errors


def main() -> int:
    failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp in (1280, 390):
            ctx = browser.new_context(viewport={"width": vp, "height": 900})
            page = ctx.new_page()
            for path in PAGES:
                errs = check(page, path)
                tag = f"{path} @{vp}"
                if errs:
                    failed += 1
                    print("FAIL", tag, errs, file=sys.stderr)
                else:
                    print("OK", tag)
            ctx.close()
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
