#!/usr/bin/env python3
"""Download one JPG from public OneDrive Photos JAY by filename (keyboard scroll + preview blob)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SHARE = "https://1drv.ms/f/c/4fe57eafc01b9140/IgBg073ovH8TR5avqJLb3Sb4AXetUTShXdEsbAseHFak2Ec"
DEFAULT_DEST = Path("/tmp/windows-photos-jay")


def download(filename: str, dest_dir: Path = DEFAULT_DEST) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / filename
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(SHARE, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(2500)
        page.locator('[role="grid"]').first.click()
        page.keyboard.press("Home")
        page.wait_for_timeout(400)
        for _ in range(2500):
            if page.get_by_text(filename, exact=True).count():
                break
            page.keyboard.press("ArrowDown")
        else:
            browser.close()
            raise FileNotFoundError(f"{filename} not found in Photos JAY grid")
        page.get_by_text(filename, exact=True).click()
        page.wait_for_timeout(3000)
        src = page.locator('[data-automation-id="oneup-image-frame"]').get_attribute("src")
        if not src or not src.startswith("blob:"):
            browser.close()
            raise RuntimeError(f"No preview blob for {filename}")
        b64 = page.evaluate(
            """async (src) => {
                const r = await fetch(src);
                const buf = await r.arrayBuffer();
                let s = '';
                const bytes = new Uint8Array(buf);
                for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
                return btoa(s);
            }""",
            src,
        )
        out.write_bytes(base64.b64decode(b64))
        browser.close()
    return out


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "THT-52.jpg"
    path = download(name)
    print(path, path.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
