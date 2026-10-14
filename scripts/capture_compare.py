#!/usr/bin/env python3
"""Side-by-side screenshots: production vs local patched bundles."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

PROD = "https://trois-heures-trente.com"
LOCAL = "http://127.0.0.1:8080"
OUT = Path("/opt/cursor/artifacts/compare")
PAGES = [
    ("home", "/", "/"),
    ("cherche", "/cherche-en-corps", "/cherche-en-corps"),
    ("fleur", "/fleur", "/fleur"),
    ("windows", "/windows", "/windows"),
    ("contact", "/contact", "/contact"),
]
VIEWPORTS = [("desktop", 1280, 900), ("mobile", 390, 844)]


def shot(page, url: str, path: Path) -> None:
    page.goto(url, wait_until="load", timeout=120000)
    page.wait_for_selector("[data-screen-label]", timeout=120000)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(path), full_page=True)


def stitch(a: Path, b: Path, dest: Path) -> None:
    im1 = Image.open(a)
    im2 = Image.open(b)
    w = im1.width + im2.width
    h = max(im1.height, im2.height)
    out = Image.new("RGB", (w, h), (8, 9, 12))
    out.paste(im1, (0, 0))
    out.paste(im2, (im1.width, 0))
    out.save(dest, quality=85)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for vp_name, width, height in VIEWPORTS:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            for slug, prod_path, local_path in PAGES:
                prod_p = OUT / f"{slug}-{vp_name}-prod.png"
                local_p = OUT / f"{slug}-{vp_name}-branch.png"
                shot(page, PROD + prod_path, prod_p)
                shot(page, LOCAL + local_path, local_p)
                stitch(prod_p, local_p, OUT / f"{slug}-{vp_name}-side-by-side.png")
                print(slug, vp_name, "ok")
            context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
