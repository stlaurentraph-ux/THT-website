#!/usr/bin/env python3
"""Generate THT favicon set from assets/source/tht-logo-black.svg."""

from __future__ import annotations

import io
import json
import re
import shutil
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source" / "tht-logo-black.svg"
OUT_DIR = ROOT / "assets" / "icons"
ASSETS = ROOT / "assets"
ROOT_ICO = ROOT / "favicon.ico"

# Square crop around the first lowercase "t" in "trois" (most legible tab mark).
CROP_VIEWBOX = (73.4, 51.2, 280.0, 764.4)
PAD_RATIO = 0.12
LIGHT_BG = (255, 255, 255, 255)
CORNER_RADIUS_RATIO = 0.18


def cropped_svg_bytes() -> bytes:
    x, y, w, h = CROP_VIEWBOX
    source_text = SOURCE.read_text(encoding="utf-8")
    inner = re.sub(r"<svg[^>]*>", "", source_text, count=1)
    inner = re.sub(r"</svg>\s*$", "", inner).strip()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}">'
        f"{inner}</svg>"
    )
    return svg.encode("utf-8")


def render_crop(size: int, background: tuple[int, ...] | None) -> Image.Image:
    x, y, w, h = CROP_VIEWBOX
    png_bytes = cairosvg.svg2png(
        bytestring=cropped_svg_bytes(),
        output_width=int(size * (w / h)),
        output_height=size,
    )
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    # Trim transparent margins, then pad to square.
    bbox = img.getbbox()
    if not bbox:
        raise RuntimeError("Empty render from logo SVG")
    cropped = img.crop(bbox)
    cw, ch = cropped.size
    side = max(cw, ch)
    pad = int(side * PAD_RATIO)
    canvas = Image.new("RGBA", (side + 2 * pad, side + 2 * pad), (0, 0, 0, 0))
    ox = pad + (side - cw) // 2
    oy = pad + (side - ch) // 2
    canvas.paste(cropped, (ox, oy), cropped)
    if background:
        bg = Image.new("RGBA", canvas.size, background)
        bg.paste(canvas, (0, 0), canvas)
        canvas = bg
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def with_rounded_bg(img: Image.Image, bg: tuple[int, ...]) -> Image.Image:
    size = img.size[0]
    radius = max(4, int(size * CORNER_RADIUS_RATIO))
    base = Image.new("RGBA", (size, size), bg)
    mask = rounded_mask(size, radius)
    composed = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    composed.paste(base, (0, 0))
    fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fg.paste(img, (0, 0), img)
    composed = Image.composite(fg, composed, mask)
    return composed


def write_png(path: Path, img: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGBA").save(path, optimize=True)


def write_svg_favicon(path: Path, *, dark_tab: bool) -> None:
    """SVG favicon with optional white rounded plate for dark browser chrome."""
    x, y, w, h = CROP_VIEWBOX
    source_text = SOURCE.read_text(encoding="utf-8")
    inner = re.sub(r"<svg[^>]*>", "", source_text, count=1)
    inner = re.sub(r"</svg>\s*$", "", inner).strip()
    plate = '<rect width="32" height="32" rx="6" fill="#ffffff"/>' if dark_tab else ""
    margin = 4
    inner_size = 32 - 2 * margin
    scale = inner_size / w
    tx = margin - x * scale
    ty = margin - y * scale + (inner_size - h * scale) / 2
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  {plate}
  <g transform="translate({tx:.4f} {ty:.4f}) scale({scale:.6f})">
    {inner}
  </g>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def write_ico(path: Path, sizes: list[int]) -> None:
    images = [render_crop(s, LIGHT_BG if s <= 48 else None) for s in sizes]
    images[0].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


def write_webmanifest(path: Path) -> None:
    manifest = {
        "name": "Compagnie THT (Trois Heures Trente)",
        "short_name": "THT",
        "icons": [
            {
                "src": "/assets/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": "/assets/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
            },
        ],
        "theme_color": "#08090c",
        "background_color": "#ffffff",
        "display": "standalone",
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"Missing logo source: {SOURCE}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # PNG / ICO sizes
    for size in (16, 32, 180, 192, 512):
        img = render_crop(size, LIGHT_BG if size <= 32 else None)
        if size >= 180:
            img = with_rounded_bg(img, LIGHT_BG)
        name = {
            16: "favicon-16.png",
            32: "favicon-32.png",
            180: "apple-touch-icon.png",
            192: "icon-192.png",
            512: "icon-512.png",
        }[size]
        write_png(OUT_DIR / name, img)

    write_ico(ROOT / "favicon.ico", [16, 32, 48])
    shutil.copy2(ROOT / "favicon.ico", ASSETS / "favicon.ico")

    # SVG favicons: transparent (light tabs) + white plate (dark tabs)
    write_svg_favicon(ASSETS / "favicon.svg", dark_tab=False)
    write_svg_favicon(ASSETS / "favicon-dark.svg", dark_tab=True)

    write_webmanifest(ASSETS / "site.webmanifest")
    print("Generated favicons in assets/icons and assets/favicon.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
