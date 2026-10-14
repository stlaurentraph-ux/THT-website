#!/usr/bin/env python3
"""Enumerate all JPGs in public OneDrive Photos JAY folder (scroll + search + parent)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SHARE = "https://1drv.ms/f/c/4fe57eafc01b9140/IgBg073ovH8TR5avqJLb3Sb4AXetUTShXdEsbAseHFak2Ec"
PARENT = "https://1drv.ms/f/c/4fe57eafc01b9140/IgBg073ovH8TR5avqJLb3Sb4AXetUTShXdEsbAseHFak2Ec"  # same redeem; navigate up in UI

NAME_RE = re.compile(r"THT[-_ ]?\d+\.jpe?g", re.I)


def collect_from_page(page) -> set[str]:
    names: set[str] = set()
    for row in page.locator('[role="row"]').all_inner_texts():
        first = row.split("\n")[0].strip()
        if first.lower().endswith((".jpg", ".jpeg")):
            names.add(first)
    for m in NAME_RE.findall(page.content()):
        n = m.replace("_", "-").replace(" ", "")
        if not n.lower().endswith(".jpg"):
            n = re.sub(r"\.jpe?g$", ".jpg", n, flags=re.I)
        names.add(n)
    return names


def scroll_list(page, *, max_steps: int = 800) -> set[str]:
    names: set[str] = set()
    grid = page.locator('[role="grid"]').first
    grid.click(timeout=5000)
    page.keyboard.press("Home")
    page.wait_for_timeout(400)
    stale = 0
    for i in range(max_steps):
        names |= collect_from_page(page)
        before = len(names)
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(60)
        if i % 40 == 0:
            page.keyboard.press("PageDown")
            page.wait_for_timeout(200)
        names |= collect_from_page(page)
        if len(names) == before:
            stale += 1
        else:
            stale = 0
        if stale > 120:
            break
    return names


def try_search(page, query: str) -> set[str]:
    names: set[str] = set()
    for sel in (
        '[data-automationid="searchbox"] input',
        'input[placeholder*="Search"]',
        'input[aria-label*="Search"]',
    ):
        loc = page.locator(sel)
        if not loc.count():
            continue
        loc.first.click()
        loc.first.fill(query)
        page.wait_for_timeout(2500)
        names |= collect_from_page(page)
        loc.first.fill("")
        page.wait_for_timeout(1000)
        break
    return names


def main() -> int:
    all_names: set[str] = set()
    json_blobs: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        def on_response(resp):
            try:
                if resp.status != 200:
                    return
                ct = resp.headers.get("content-type", "")
                if "json" not in ct and "javascript" not in ct:
                    return
                text = resp.text()
                if "THT-" not in text and "nextLink" not in text:
                    return
                data = json.loads(text)
                json_blobs.append(data)
            except Exception:
                pass

        page.on("response", on_response)

        page.goto(SHARE, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)
        all_names |= scroll_list(page)
        for q in ("THT-52", "THT-052", "THT_52", "52.jpg", "THT-252"):
            all_names |= try_search(page, q)

        # Parent: Windows (breadcrumb)
        for crumb in ("Windows", "THT"):
            loc = page.get_by_role("link", name=crumb)
            if loc.count():
                loc.first.click()
                page.wait_for_timeout(3000)
                all_names |= scroll_list(page, max_steps=200)
                page.goto(SHARE, wait_until="networkidle", timeout=120000)
                page.wait_for_timeout(2000)

        # Subfolders under Photos JAY
        page.goto(SHARE, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(2000)
        for folder in page.locator('[role="gridcell"]:has-text("folder"), [data-item-type="folder"]').all()[:10]:
            try:
                t = folder.inner_text(timeout=500)
                if t:
                    folder.dblclick(timeout=3000)
                    page.wait_for_timeout(2500)
                    all_names |= scroll_list(page, max_steps=200)
                    page.go_back()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

        browser.close()

    for blob in json_blobs:
        stack = [blob]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if "name" in cur and str(cur["name"]).lower().endswith((".jpg", ".jpeg")):
                    all_names.add(cur["name"])
                if "value" in cur:
                    stack.extend(cur["value"])
                if "@odata.nextLink" in cur:
                    pass  # logged separately
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)

    jpg = sorted(
        {n for n in all_names if n.lower().endswith((".jpg", ".jpeg"))},
        key=lambda x: int(re.search(r"(\d+)", x).group(1)) if re.search(r"(\d+)", x) else 0,
    )

    out = Path("/opt/cursor/artifacts/jay-onedrive-enumeration.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"count": len(jpg), "files": jpg, "raw_name_count": len(all_names)}, indent=2),
        encoding="utf-8",
    )
    print(f"JPG count: {len(jpg)}")
    print(f"Written: {out}")
    for variant in ("THT-52.jpg", "THT-052.jpg", "THT_52.jpg", "THT-52 .jpg", "THT-252.jpg"):
        print(variant, "FOUND" if variant in all_names or variant in jpg else "missing")
    hits = [n for n in jpg if re.search(r"(^|THT[-_]?0?52\.|252)", n, re.I)]
    print("52-related:", hits)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
