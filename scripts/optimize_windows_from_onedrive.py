#!/usr/bin/env python3
"""Optimize curated WINDOWS photos (Photos JAY) into assets/images/windows/."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "images" / "windows"
SRC = Path("/tmp/windows-photos-jay")
TARGET_KB = 200
MAX_WIDTH = 1600

# Raphaël picks (Photos JAY).
FILES = [
    ("hero", "THT-104.jpg"),
    ("og-windows", "THT-104.jpg"),
    ("g01", "THT-195.jpg"),
    ("g02", "THT-24.jpg"),
    ("g03", "THT-52.jpg"),
]
TILE = "THT-232.jpg"


def save_webp(im: Image.Image, dest: Path, target_kb: int = TARGET_KB) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = im.convert("RGB") if im.mode in ("RGBA", "P") else im
    w, h = im.size
    if w > MAX_WIDTH:
        im = im.resize((MAX_WIDTH, int(h * MAX_WIDTH / w)), Image.Resampling.LANCZOS)
    for q in (82, 78, 72, 65, 58, 50):
        im.save(dest, "WEBP", quality=q, method=6)
        if dest.stat().st_size <= target_kb * 1024:
            return dest.stat().st_size
    return dest.stat().st_size


def main() -> int:
    src_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC
    if not src_dir.is_dir():
        print(f"Missing source dir: {src_dir}", file=sys.stderr)
        return 1
    for slug, name in FILES:
        src = src_dir / name
        if not src.exists():
            print(f"Missing {src}", file=sys.stderr)
            return 1
        with Image.open(src) as im:
            out = OUT / f"{slug}.webp"
            size = save_webp(im, out)
            print(f"{out.name} ← {name}: {size // 1024} KB")
    with Image.open(src_dir / TILE) as im:
        save_webp(im, OUT / "tile.webp")
    print(f"tile.webp ← {TILE}: {(OUT / 'tile.webp').stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
