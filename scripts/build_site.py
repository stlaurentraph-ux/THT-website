#!/usr/bin/env python3
"""Patch production Claude bundles (legacy/bundles/) → deployable HTML + /assets."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy" / "bundles"
OUT = ROOT
ASSETS = ROOT / "assets"
SITE_URL = "https://trois-heures-trente.com"
CONTACT_EMAIL = "compagnie.tht@gmail.com"
LEGACY_CONTACT_EMAIL = bytes.fromhex(
    "636f6e746163744074726f69732d6865757265732d7472656e74652e636f6d"
).decode()
ORG_LOGO = f"{SITE_URL}/assets/favicon.svg"
ORG_SAME_AS = [
    "https://www.instagram.com/compagnie_tht/",
    "https://www.youtube.com/@THTCompagnie",
    "https://www.linkedin.com/company/compagnie-tht/",
    "https://www.facebook.com/share/1AfcmtsWT7/",
]
CHERCHE_TEASER_URL = "https://www.youtube.com/watch?v=TjewwAOC488"
CHERCHE_TEASER_EMBED = "https://www.youtube.com/embed/TjewwAOC488"

PAGES = [
    "index.html",
    "cherche-en-corps.html",
    "fleur.html",
    "windows.html",
    "ateliers.html",
    "contact.html",
]

CEC_PDF = "/assets/docs/THT_Cherche-en-corps_01_presentation.pdf"
FLEUR_DIR = "/assets/images/fleur"
FLEUR_HERO = f"{FLEUR_DIR}/hero.webp"
FLEUR_OG = f"{SITE_URL}{FLEUR_DIR}/og-fleur.webp"
FLEUR_GALLERY = [f"{FLEUR_DIR}/g{i:02d}.webp" for i in range(1, 9)]

WINDOWS_DIR = "/assets/images/windows"
WINDOWS_HERO = f"{WINDOWS_DIR}/hero.webp"
WINDOWS_OG = f"{SITE_URL}{WINDOWS_DIR}/og-windows.webp"
WINDOWS_GALLERY = [f"{WINDOWS_DIR}/g{i:02d}.webp" for i in range(1, 4)]

WP_REPLACEMENTS = {
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-114-scaled.jpg": f"{WINDOWS_DIR}/g01.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-63-scaled.jpg": f"{FLEUR_DIR}/tile.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-241-scaled.jpg": f"{WINDOWS_DIR}/tile.webp",
    "https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-52-2-scaled.jpg": FLEUR_HERO,
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/THT-329-scaled.jpg": WINDOWS_HERO,
    "https://www.trois-heures-trente.com/wp-content/uploads/2025/08/Portrait-de-CEC-FR-Presentation-1-768x1024.png": CEC_PDF,
}

FLEUR_WP_TO_ASSET = {
    "https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-52-2-scaled.jpg": FLEUR_HERO,
    "https://www.trois-heures-trente.com/wp-content/uploads/2023/08/Ouili_fleur-63-scaled.jpg": f"{FLEUR_DIR}/tile.webp",
}

PAGE_META: dict[str, dict[str, str]] = {
    "index.html": {
        "fr": {
            "title": "Compagnie THT | Danse hip-hop et contemporaine",
            "description": "Compagnie THT (Trois Heures Trente): créations FLEUR, Cherche en Corps, WINDOWS. Hip-hop et danse contemporaine, Carrières-sous-Poissy et Oslo.",
        },
        "en": {
            "title": "THT Company | Hip-hop and contemporary dance",
            "description": "THT Company (Trois Heures Trente): FLEUR, Cherche en Corps, WINDOWS. Hip-hop meets contemporary dance, based in France and Norway.",
        },
    },
    "cherche-en-corps.html": {
        "fr": {
            "title": "Cherche en Corps | Compagnie THT",
            "description": "Cherche en Corps, duo de Ouili Nana et Raphaël Saint-Laurent. Teaser, captation intégrale et tournée. Compagnie THT.",
        },
        "en": {
            "title": "Cherche en Corps | THT Company",
            "description": "Cherche en Corps, a duo by Ouili Nana and Raphaël Saint-Laurent. Teaser, full recording, and tour dates. THT Company.",
        },
    },
    "fleur.html": {
        "fr": {
            "title": "FLEUR | Solo de Ouili Nana | Compagnie THT",
            "description": "FLEUR, solo hip-hop de Ouili Nana. 50 minutes, compagnie THT.",
        },
        "en": {
            "title": "FLEUR | Solo by Ouili Nana | THT Company",
            "description": "FLEUR, a hip-hop solo by Ouili Nana. 50 minutes, THT Company.",
        },
    },
    "windows.html": {
        "fr": {
            "title": "WINDOWS | Compagnie THT",
            "description": "WINDOWS, création 2025 chorégraphiée par Ouili Nana. Trio hip-hop et lumière.",
        },
        "en": {
            "title": "WINDOWS | THT Company",
            "description": "WINDOWS, 2025 creation choreographed by Ouili Nana. A hip-hop trio in light and shadow.",
        },
    },
    "ateliers.html": {
        "fr": {
            "title": "Ateliers | Compagnie THT",
            "description": "Ateliers de transmission: hip-hop, freestyle et création avec la compagnie THT.",
        },
        "en": {
            "title": "Workshops | THT Company",
            "description": "Workshops in hip-hop, freestyle, and creation with THT Company.",
        },
    },
    "contact.html": {
        "fr": {
            "title": "Contact | Compagnie THT",
            "description": f"Contact et diffusion: {CONTACT_EMAIL}. Compagnie THT, Carrières-sous-Poissy.",
        },
        "en": {
            "title": "Contact | THT Company",
            "description": f"Booking and contact: {CONTACT_EMAIL}. THT Company, France.",
        },
    },
}


def fix_contact_email(text: str) -> str:
    return text.replace(LEGACY_CONTACT_EMAIL, CONTACT_EMAIL)


def page_path(page: str, lang: str) -> str:
    slug = page.replace(".html", "")
    if slug == "index":
        return "/" if lang == "fr" else "/en/"
    return f"/{slug}" if lang == "fr" else f"/en/{slug}"


def ld_json_script_tag(page: str, lang: str) -> str:
    graph = ld_json_graph(page, lang)
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    payload = payload.replace("</", "<\\/")
    return f'  <script type="application/ld+json">{payload}</script>'


def ld_json_graph(page: str, lang: str) -> list[dict]:
    path = page_path(page, lang)
    canonical = SITE_URL + path
    org_id = f"{SITE_URL}/#organization"
    home_label = "Accueil" if lang == "fr" else "Home"
    home_url = SITE_URL + ("/" if lang == "fr" else "/en/")

    org: dict = {
        "@type": ["DanceGroup", "PerformingGroup", "Organization"],
        "@id": org_id,
        "name": "Compagnie THT (Trois Heures Trente)",
        "alternateName": "THT Company" if lang == "en" else "Trois Heures Trente",
        "url": SITE_URL,
        "logo": ORG_LOGO,
        "email": CONTACT_EMAIL,
        "founder": {"@type": "Person", "name": "Ouili Nana"},
        "sameAs": ORG_SAME_AS,
    }

    crumbs: list[dict] = [{"@type": "ListItem", "position": 1, "name": home_label, "item": home_url}]
    if page != "index.html":
        crumbs.append(
            {
                "@type": "ListItem",
                "position": 2,
                "name": PAGE_META[page][lang]["title"].split("|")[0].strip(),
                "item": canonical,
            }
        )
    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{canonical}#breadcrumb",
        "itemListElement": crumbs,
    }

    graph: list[dict] = [org, breadcrumb]

    if page == "fleur.html":
        graph.append(
            {
                "@type": ["CreativeWork", "TheaterEvent"],
                "@id": f"{canonical}#fleur",
                "name": "FLEUR",
                "url": canonical,
                "description": PAGE_META[page][lang]["description"],
                "duration": "PT50M",
                "creator": {"@type": "Person", "name": "Ouili Nana"},
                "performer": {"@type": "Person", "name": "Ouili Nana"},
                "organizer": {"@id": org_id},
            }
        )
    elif page == "cherche-en-corps.html":
        graph.append(
            {
                "@type": ["CreativeWork", "TheaterEvent"],
                "@id": f"{canonical}#cherche-en-corps",
                "name": "Cherche en Corps",
                "url": canonical,
                "description": PAGE_META[page][lang]["description"],
                "duration": "PT50M",
                "creator": {"@type": "Person", "name": "Ouili Nana"},
                "performer": [
                    {"@type": "Person", "name": "Ouili Nana"},
                    {"@type": "Person", "name": "Raphaël Saint-Laurent"},
                ],
                "organizer": {"@id": org_id},
            }
        )
        graph.append(
            {
                "@type": "VideoObject",
                "@id": f"{canonical}#teaser",
                "name": "Cherche en Corps — teaser" if lang == "fr" else "Cherche en Corps — teaser",
                "url": CHERCHE_TEASER_URL,
                "embedUrl": CHERCHE_TEASER_EMBED,
                "publisher": {"@id": org_id},
            }
        )
    elif page == "windows.html":
        graph.append(
            {
                "@type": ["CreativeWork", "TheaterEvent"],
                "@id": f"{canonical}#windows",
                "name": "WINDOWS",
                "url": canonical,
                "description": PAGE_META[page][lang]["description"],
                "dateCreated": "2025",
                "creator": {"@type": "Person", "name": "Ouili Nana"},
                "performer": {"@type": "Person", "name": "Ouili Nana"},
                "organizer": {"@id": org_id},
            }
        )

    return graph


def _script_json_payload(html: str, script_type: str, *, close_from_end: bool = False) -> str:
    """Extract JSON text from a bundler script tag."""
    open_tag = f'<script type="{script_type}">'
    start = html.index(open_tag) + len(open_tag)
    if close_from_end:
        end = html.rindex("</script>", start)
    else:
        end = html.index("</script>", start)
    return html[start:end].strip()


def json_for_script_embed(value: str) -> str:
    """Serialize a string for embedding in <script type=\"__bundler/template\"> without closing the host tag."""
    payload = json.dumps(value, ensure_ascii=False)
    # Match production bundles: escape closing HTML tags inside the JSON string.
    return payload.replace("</", r"<\u002F")


def parse_bundle(path: Path | str) -> tuple[dict, str]:
    text = path if isinstance(path, str) else path.read_text(encoding="utf-8")
    manifest = json.loads(
        _script_json_payload(html=text, script_type="__bundler/manifest", close_from_end=False)
    )
    template = json.loads(
        _script_json_payload(html=text, script_type="__bundler/template", close_from_end=True)
    )
    return manifest, template


def split_locales(template: str) -> tuple[str, str]:
    parts = re.split(
        r'<sc-if value="\{\{ isFr \}\}"[^>]*>|<sc-if value="\{\{ isEn \}\}"[^>]*>|</sc-if>',
        template,
    )
    fr = parts[1] if len(parts) > 1 else template
    en = parts[3] if len(parts) > 3 else ""
    return fr, en


def extract_helmet_styles(template: str) -> str:
    m = re.search(r"<style>(.*?)</style>", template, re.DOTALL)
    return m.group(1) if m else ""


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:80] or "image"


def decode_asset_data(data: str) -> bytes:
    if data.startswith("data:"):
        return __import__("base64").b64decode(data.split(",", 1)[1])
    return __import__("base64").b64decode(data)


def optimize_image(src: Path, dest: Path, max_width: int = 1920) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        shutil.copy2(src, dest.with_suffix(src.suffix))
        return

    with Image.open(src) as im:
        im = im.convert("RGB") if im.mode in ("RGBA", "P") else im
        w, h = im.size
        if w > max_width:
            im = im.resize((max_width, int(h * max_width / w)), Image.Resampling.LANCZOS)
        im.save(dest, "WEBP", quality=82, method=6)


def collect_assets() -> dict[str, str]:
    """Extract images/fonts from legacy bundles; return uuid -> public URL map."""
    uuid_map: dict[str, str] = {}
    raw_dir = ASSETS / "_raw"
    img_dir = ASSETS / "images"
    font_dir = ASSETS / "fonts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)
    font_dir.mkdir(parents=True, exist_ok=True)

    seen_fonts: set[str] = set()

    for page in PAGES:
        bundle_path = LEGACY / page
        if not bundle_path.exists():
            continue
        manifest, template = parse_bundle(bundle_path)
        for uid, meta in manifest.items():
            if not isinstance(meta, dict):
                continue
            mime = meta.get("mime", "")
            data = meta.get("data", "")
            if not data:
                continue
            if mime.startswith("image/"):
                if uid in uuid_map:
                    continue
                alt_m = re.search(
                    rf'src="{re.escape(uid)}"[^>]*alt="([^"]*)"|alt="([^"]*)"[^>]*src="{re.escape(uid)}"',
                    template,
                )
                alt = (alt_m.group(1) or alt_m.group(2) or uid) if alt_m else uid
                ext = ".png" if "png" in mime else ".jpg"
                raw = raw_dir / f"{slugify(alt)}-{uid[:8]}{ext}"
                if not raw.exists():
                    raw.write_bytes(decode_asset_data(data))
                webp = img_dir / f"{slugify(alt)}-{uid[:8]}.webp"
                if not webp.exists():
                    optimize_image(raw, webp)
                uuid_map[uid] = f"/assets/images/{webp.name}"
            elif mime == "font/woff2" and uid not in seen_fonts:
                seen_fonts.add(uid)
                out = font_dir / f"{uid}.woff2"
                if not out.exists():
                    out.write_bytes(decode_asset_data(data))
                uuid_map[uid] = f"/assets/fonts/{out.name}"

    return uuid_map


def replace_uuids(html: str, uuid_map: dict[str, str], *, include_fonts: bool = True) -> str:
    for uid, url in sorted(uuid_map.items(), key=lambda x: -len(x[0])):
        if not include_fonts and url.startswith("/assets/fonts/"):
            continue
        html = html.replace(f'"{uid}"', f'"{url}"')
        html = html.replace(f"url({uid})", f"url({url})")
        html = html.replace(f'url("{uid}")', f'url("{url}")')
    return html


def fix_internal_links(html: str, lang: str, page: str) -> str:
    prefix = "" if lang == "fr" else "/en"
    other_prefix = "/en" if lang == "fr" else ""

    for name in PAGES:
        base = name.replace(".html", "")
        if lang == "fr":
            html = html.replace(f'href="{name}"', f'href="/{base}"')
            html = html.replace(f'href="/{base}"', f'href="/{base}"')  # idempotent
        else:
            html = html.replace(f'href="{name}"', f'href="/en/{base}"')

    html = re.sub(
        r'<span style="color:rgba\(233,236,242,.4\)">\[\s*<span style="color:#5ec9ff">fr</span>/<span sc-camel-on-click="\{\{ setIsEn \}\}"[^>]*>en</span>\s*\]</span>',
        f'<span style="color:rgba(233,236,242,.4)">[<a href="{other_prefix or "/"}" style="color:#5ec9ff;text-decoration:none">fr</a>/<a href="{prefix or "/"}" style="color:#5ec9ff;text-decoration:none">en</a>]</span>',
        html,
    )
    html = re.sub(
        r'<span style="color:rgba\(233,236,242,.4\)">\[\s*<span sc-camel-on-click="\{\{ setIsFr \}\}"[^>]*>fr</span>/<span style="color:#5ec9ff">en</span>\s*\]</span>',
        f'<span style="color:rgba(233,236,242,.4)">[<a href="{other_prefix or "/"}" style="color:#5ec9ff;text-decoration:none">fr</a>/<a href="{prefix or "/"}" style="color:#5ec9ff;text-decoration:none">en</a>]</span>',
        html,
    )
    if lang == "en" and page == "index.html":
        html = html.replace('href="/"', 'href="/en/"')
    return html


def strip_react_artifacts(html: str) -> str:
    html = re.sub(r"<script src=\"[^\"]+\"></script>", "", html)
    html = re.sub(r"<x-dc>|</x-dc>|<helmet[^>]*>|</helmet>", "", html)
    html = re.sub(r"\sdata-screen-label=\"[^\"]*\"", "", html)
    html = re.sub(r"\ssc-camel-[a-z-]+=\"[^\"]*\"", "", html)
    html = re.sub(r"\shint-placeholder-val=\"[^\"]*\"", "", html)
    return html


def replace_url_everywhere(text: str, old: str, new: str) -> str:
    text = text.replace(old, new)
    esc = old.replace("/", "\\/")
    if esc != old:
        text = text.replace(esc, new.replace("/", "\\/"))
    return text


def fix_wp_urls(html: str) -> str:
    for old, new in WP_REPLACEMENTS.items():
        html = replace_url_everywhere(html, old, new)
    for old, new in FLEUR_WP_TO_ASSET.items():
        html = replace_url_everywhere(html, old, new)
    return replace_remaining_wp_images(html)


def replace_remaining_wp_images(html: str) -> str:
    """Swap any leftover WordPress URLs (404) for local WebP gallery images."""
    img_dir = ASSETS / "images"
    pool = sorted(img_dir.glob("*.webp"))
    if not pool:
        return html
    pool_paths = [f"/assets/images/{p.name}" for p in pool if p.name != "og-default.webp"]
    if not pool_paths:
        pool_paths = [f"/assets/images/{pool[0].name}"]
    i = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal i
        url = pool_paths[i % len(pool_paths)]
        i += 1
        return match.group(0).replace(match.group(1), url)

    html = re.sub(
        r'src="(https://www\.trois-heures-trente\.com/wp-content/uploads/[^"]+)"',
        repl,
        html,
    )
    html = re.sub(
        r'href="(https://www\.trois-heures-trente\.com/wp-content/uploads/[^"]+)"',
        lambda m: f'href="mailto:{CONTACT_EMAIL}?subject=Dossier%20FLEUR"',
        html,
    )
    return html


def newsletter_block(lang: str) -> str:
    if lang == "fr":
        title, sub = "Restez dans la boucle", "Dates, créations, battles: quelques mails par saison."
        l_name, l_email, l_city, l_org = "Nom", "Adresse e-mail", "Ville (facultatif)", "Organisation (facultatif)"
        consent = (
            "J'accepte que mes données (nom, e-mail, ville et organisation) soient enregistrées "
            "pour recevoir la newsletter de la Compagnie THT. Je peux retirer mon consentement "
            f"à tout moment via {CONTACT_EMAIL} (RGPD)."
        )
        btn, loading = "S'inscrire", "Envoi…"
        ok, err = "Merci, vous êtes inscrit·e.", "Impossible de finaliser l'inscription. Réessayez ou écrivez-nous."
    else:
        title, sub = "Stay in the loop", "Tour dates, new work, a few emails per season."
        l_name, l_email, l_city, l_org = "Name", "Email address", "City (optional)", "Organisation (optional)"
        consent = (
            "I agree that my details (name, email, city, organisation) may be stored to send me "
            f"THT Company news. I can withdraw consent anytime at {CONTACT_EMAIL} (GDPR)."
        )
        btn, loading = "Subscribe", "Sending…"
        ok, err = "Thank you, you are subscribed.", "We could not complete signup. Please try again or email us."
    field = (
        "width:100%;background:transparent;border:1px solid rgba(233,236,242,.35);"
        "color:#e9ecf2;padding:12px 14px;font:400 12px 'IBM Plex Mono',monospace;outline:none"
    )
    return (
        f'<section id="newsletter" aria-labelledby="newsletter-title" '
        f'style="padding:36px 44px;border-bottom:1px solid rgba(233,236,242,.12);background:#08090c;color:#e9ecf2">'
        f'<div style="display:grid;grid-template-columns:1fr 1.2fr;gap:40px;align-items:start">'
        f'<div style="display:flex;flex-direction:column;gap:8px">'
        f'<h2 id="newsletter-title" style="margin:0;font:400 26px \'Bebas Neue\',sans-serif;letter-spacing:.05em">{title}</h2>'
        f'<p style="margin:0;font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55)">{sub}</p></div>'
        f'<form action="/api/subscribe" method="post" data-newsletter-form '
        f'data-msg-success="{ok}" data-msg-error="{err}" style="display:flex;flex-direction:column;gap:14px;margin:0">'
        f'<input type="hidden" name="lang" value="{lang}">'
        f'<div style="position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden" aria-hidden="true">'
        f'<label for="nl-hp-{lang}">Leave blank</label>'
        f'<input id="nl-hp-{lang}" name="company_website" type="text" tabindex="-1" autocomplete="off"></div>'
        f'<div><label for="nl-name-{lang}" style="display:block;font:400 10px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:6px;letter-spacing:.08em">{l_name} *</label>'
        f'<input id="nl-name-{lang}" name="name" type="text" required autocomplete="name" style="{field}"></div>'
        f'<div><label for="nl-email-{lang}" style="display:block;font:400 10px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:6px;letter-spacing:.08em">{l_email} *</label>'
        f'<input id="nl-email-{lang}" name="email" type="email" required autocomplete="email" style="{field}"></div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">'
        f'<div><label for="nl-city-{lang}" style="display:block;font:400 10px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.6);margin-bottom:6px">{l_city}</label>'
        f'<input id="nl-city-{lang}" name="city" type="text" autocomplete="address-level2" style="{field}"></div>'
        f'<div><label for="nl-org-{lang}" style="display:block;font:400 10px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.6);margin-bottom:6px">{l_org}</label>'
        f'<input id="nl-org-{lang}" name="organisation" type="text" autocomplete="organization" style="{field}"></div></div>'
        f'<label style="display:flex;gap:10px;align-items:flex-start;font:400 11px/1.5 \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.65);cursor:pointer">'
        f'<input name="consent" type="checkbox" value="1" required style="margin-top:3px">'
        f'<span>{consent}</span></label>'
        f'<button type="submit" data-loading="{loading}" '
        f'style="align-self:flex-start;background:#5ec9ff;color:#08090c;border:0;padding:12px 24px;'
        f'font:500 12px \'IBM Plex Mono\',monospace;cursor:pointer">{btn}</button>'
        f'<p data-newsletter-status hidden style="margin:0;font:400 12px \'IBM Plex Mono\',monospace"></p>'
        f"</form></div></section>"
        f'<script src="/assets/js/newsletter.js" defer></script>'
    )


def fix_newsletter(html: str, lang: str) -> str:
    block = newsletter_block(lang)
    patterns = [
        re.compile(
            r'<div style="display:flex;justify-content:space-between;align-items:center;gap:40px;padding:36px 44px;border-bottom:1px solid rgba\(233,236,242,.12\)">.*?</div>',
            re.DOTALL,
        ),
        re.compile(
            r'<div style="display:flex;justify-content:space-between;align-items:center;gap:40px;padding:36px 44px;border-bottom:1px solid rgba\(233,236,242,.12\)">\s*'
            r'<div style="display:flex;flex-direction:column;gap:6px">.*?'
            r'<div style="display:flex;gap:0">.*?</div>\s*</div>',
            re.DOTALL,
        ),
    ]
    for pat in patterns:
        if pat.search(html):
            html = pat.sub(block, html, count=1)
            break
    html = re.sub(
        r'<div style="display:flex;gap:0"><input placeholder="[^"]*".*?</div>\s*',
        "",
        html,
        count=1,
    )
    return html


CHERCHE_LOGO = "/assets/images/cherche-en-corps-logo.png"


def ensure_cherche_logo_asset() -> None:
    """Title logo PNG with transparent background (source bundle asset is flat grey)."""
    src = ASSETS / "images" / "cherche-en-corps-45f1f032.webp"
    dest = ASSETS / "images" / "cherche-en-corps-logo.png"
    if not src.exists():
        return
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(src).convert("RGBA")
    bg = im.getpixel((0, 0))[:3]
    tol = 28
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if (
                abs(r - bg[0]) <= tol
                and abs(g - bg[1]) <= tol
                and abs(b - bg[2]) <= tol
            ):
                px[x, y] = (r, g, b, 0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "PNG", optimize=True)


def fix_cherche_title_logo(template: str) -> str:
    return re.sub(
        r'(<img src=")[^"]+(" alt="Cherche en Corps" style="width:480px;display:block">)',
        rf"\1{CHERCHE_LOGO}\2",
        template,
    )


def fix_cherche_videos(html: str, lang: str) -> str:
    if lang == "fr":
        block = (
            '<div style="font:400 40px \'Bebas Neue\',sans-serif;letter-spacing:.04em">Vidéos</div>'
            '<div style="display:flex;flex-direction:column;gap:20px">'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:8px;letter-spacing:.08em">TEASER</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/TjewwAOC488" title="Cherche en Corps — teaser" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>'
            '<p style="margin:10px 0 0;font:400 12px/1.6 \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.65)">'
            '<a href="/contact" style="color:#5ec9ff;text-decoration:none">Contactez-nous pour obtenir la captation complète.</a></p></div>'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55);margin-bottom:8px;letter-spacing:.08em">RÉFÉRENCE · SAN FRANCISCO</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/K9OICzieSfc" title="Cherche en Corps à San Francisco" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div></div>'
            "</div>"
            '<div style="display:flex;gap:20px;font:400 11px \'IBM Plex Mono\',monospace;margin-top:8px">'
            '<a href="https://www.youtube.com/@THTCompagnie" style="color:rgba(233,236,242,.7);text-decoration:none">▶ plus de vidéos sur la chaîne ↗</a></div>'
        )
    else:
        block = (
            '<div style="font:400 40px \'Bebas Neue\',sans-serif;letter-spacing:.04em">Videos</div>'
            '<div style="display:flex;flex-direction:column;gap:20px">'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:#5ec9ff;margin-bottom:8px;letter-spacing:.08em">TEASER</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/TjewwAOC488" title="Cherche en Corps — teaser" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>'
            '<p style="margin:10px 0 0;font:400 12px/1.6 \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.65)">'
            '<a href="/en/contact" style="color:#5ec9ff;text-decoration:none">Contact us to receive the full recording.</a></p></div>'
            '<div><div style="font:400 11px \'IBM Plex Mono\',monospace;color:rgba(233,236,242,.55);margin-bottom:8px;letter-spacing:.08em">REFERENCE · SAN FRANCISCO</div>'
            '<div style="aspect-ratio:16/9;background:#000;border:1px solid rgba(233,236,242,.12)">'
            '<iframe src="https://www.youtube.com/embed/K9OICzieSfc" title="Cherche en Corps in San Francisco" style="width:100%;height:100%;border:0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div></div>'
            "</div>"
            '<div style="display:flex;gap:20px;font:400 11px \'IBM Plex Mono\',monospace;margin-top:8px">'
            '<a href="https://www.youtube.com/@THTCompagnie" style="color:rgba(233,236,242,.7);text-decoration:none">▶ more on our YouTube channel ↗</a></div>'
        )

    pattern = re.compile(
        r'<div style="font:400 40px \'Bebas Neue\',sans-serif;letter-spacing:.04em">Vid[ée]os</div>.*?'
        r'<div style="display:flex;gap:20px;font:400 11px \'IBM Plex Mono\',monospace">.*?</div>',
        re.DOTALL,
    )
    return pattern.sub(block, html, count=1)


def fix_dossier_links(html: str, page: str) -> str:
    if page == "cherche-en-corps.html":
        html = re.sub(
            r'href="(?:contact\.html|/contact)"([^>]*>)dossier de diffusion ↓',
            rf'href="{CEC_PDF}" download\1dossier de diffusion ↓',
            html,
        )
        html = re.sub(
            r'href="(?:contact\.html|/en/contact)"([^>]*>)download dossier ↓',
            rf'href="{CEC_PDF}" download\1download dossier ↓',
            html,
        )
    if page == "contact.html":
        html = html.replace(
            f'href="{CEC_PDF}"',
            f'href="{CEC_PDF}"',
        )
        html = re.sub(
            r'href="https://www\.trois-heures-trente\.com/wp-content/uploads/2025/08/Portrait-de-CEC-FR-Presentation-1-768x1024\.png"',
            f'href="{CEC_PDF}" download',
            html,
        )
    return html


def apply_fleur_images(html: str) -> str:
    """Hero + gallery from LeDockerNoir photos (assets/images/fleur/)."""
    html = re.sub(
        r'(<div style="position:relative;height:620px;overflow:hidden[^"]*">\s*)'
        r'<img src="[^"]+" alt="FLEUR[^"]*" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">',
        rf'\1<img src="{FLEUR_HERO}" alt="FLEUR — Ouili Nana" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">',
        html,
        count=1,
    )
    gallery_imgs = "".join(
        f'<img src="{src}" alt="FLEUR — LeDockerNoir" style="width:100%;aspect-ratio:4/5;object-fit:cover;display:block">'
        for src in FLEUR_GALLERY
    )
    html = re.sub(
        r'<div style="display:grid;grid-template-columns:repeat\(4,1fr\);gap:1px;background:rgba\(233,236,242,.12\);border-top:1px solid rgba\(233,236,242,.12\);border-bottom:1px solid rgba\(233,236,242,.12\)">\s*'
        r'(?:<img src="[^"]+" alt="FLEUR[^"]*" style="width:100%;aspect-ratio:4/5;object-fit:cover;display:block">\s*)+'
        r"</div>",
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:rgba(233,236,242,.12);border-top:1px solid rgba(233,236,242,.12);border-bottom:1px solid rgba(233,236,242,.12)">{gallery_imgs}</div>',
        html,
        count=1,
    )
    return html


def apply_windows_gallery(template: str) -> str:
    """Hero + 3-column gallery from Photos JAY (FR + EN blocks in one template)."""
    template = re.sub(
        r'(<div style="position:relative;height:620px;overflow:hidden[^"]*">\s*)'
        r'<img src="[^"]+" (alt="WINDOWS[^"]*" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover")',
        rf'\1<img src="{WINDOWS_HERO}" \2',
        template,
    )
    gallery_imgs = "".join(
        f'<img src="{src}" alt="WINDOWS" style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block">'
        for src in WINDOWS_GALLERY
    )
    grid = (
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:rgba(233,236,242,.12);'
        f'border-top:1px solid rgba(233,236,242,.12);border-bottom:1px solid rgba(233,236,242,.12)">{gallery_imgs}</div>'
    )
    template = re.sub(
        r'<div style="display:grid;grid-template-columns:repeat\(3,1fr\);gap:1px;background:rgba\(233,236,242,.12\);border-top:1px solid rgba\(233,236,242,.12\);border-bottom:1px solid rgba\(233,236,242,.12\)">\s*'
        r'(?:<img src="[^"]+" alt="WINDOWS[^"]*" style="width:100%;aspect-ratio:4/3;object-fit:cover;display:block">\s*)+'
        r"</div>",
        grid,
        template,
    )
    return template


def fix_pronouns(html: str) -> str:
    # Bundler artifact in EN ateliers copy; Ouili Nana uses he/him elsewhere.
    html = re.sub(
        r"creative process and the .{1,48}? of Cherche en [Cc]orps\.?",
        "creative process and the making of Cherche en Corps.",
        html,
    )
    return html


def head_block(page: str, lang: str, styles: str) -> str:
    meta = PAGE_META[page][lang]
    slug = page.replace(".html", "")
    if slug == "index":
        path = "/" if lang == "fr" else "/en/"
    else:
        path = f"/{slug}" if lang == "fr" else f"/en/{slug}"
    canonical = SITE_URL + path
    alt_fr = SITE_URL + (f"/{slug}" if slug != "index" else "/")
    alt_en = SITE_URL + (f"/en/{slug}" if slug != "index" else "/en/")
    if page == "fleur.html":
        og_image = FLEUR_OG
    elif page == "windows.html":
        og_image = WINDOWS_OG
    else:
        og_image = f"{SITE_URL}/assets/images/og-default.webp"
    lang_attr = "fr" if lang == "fr" else "en"
    return f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{meta["title"]}</title>
  <meta name="description" content="{meta["description"]}">
  <link rel="canonical" href="{canonical}">
  <link rel="alternate" hreflang="fr" href="{alt_fr}">
  <link rel="alternate" hreflang="en" href="{alt_en}">
  <link rel="alternate" hreflang="x-default" href="{alt_fr}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Compagnie THT">
  <meta property="og:title" content="{meta["title"]}">
  <meta property="og:description" content="{meta["description"]}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{meta["title"]}">
  <meta name="twitter:description" content="{meta["description"]}">
  <meta name="twitter:image" content="{og_image}">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{ld_json_script_tag(page, lang)}
  <style>{styles}
  @media (max-width: 900px) {{
    [data-screen-label] {{ min-width: 0 !important; }}
    div[style*="min-width:1100px"] {{ min-width: 0 !important; }}
  }}
  </style>
</head>
<body>
"""


def build_page(page: str, lang: str, body: str, styles: str) -> str:
    html = strip_react_artifacts(body)
    html = fix_internal_links(html, lang, page)
    html = fix_wp_urls(html)
    html = fix_newsletter(html, lang)
    if page == "cherche-en-corps.html":
        html = fix_cherche_videos(html, lang)
    elif page == "index.html":
        html = re.sub(
            r'(<a href="/fleur"[^>]*><img src=")[^"]+(" alt="FLEUR")',
            rf'\1{FLEUR_DIR}/tile.webp\2',
            html,
        )
        html = re.sub(
            r'(<a href="/(?:en/)?windows"[^>]*><img src=")[^"]+(" alt="WINDOWS")',
            rf'\1{WINDOWS_DIR}/tile.webp\2',
            html,
        )
        home_hero = f"{WINDOWS_DIR}/g01.webp"
        html = re.sub(
            r'(<div style="position:relative;height:640px;overflow:hidden[^"]*">\s*)'
            r'<img src="[^"]+" alt="WINDOWS[^"]*" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">',
            rf'\1<img src="{home_hero}" alt="WINDOWS" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover">',
            html,
            count=1,
        )
        html = html.replace(
            "▶ Cherche en Corps à San Francisco",
            "▶ Cherche en Corps — teaser",
        )
        html = html.replace(
            "▶ Cherche en Corps in San Francisco",
            "▶ Cherche en Corps — teaser",
        )
        html = html.replace(
            "https://www.youtube.com/watch?v=K9OICzieSfc",
            "https://www.youtube.com/watch?v=TjewwAOC488",
        )
    html = fix_dossier_links(html, page)
    html = fix_pronouns(html)
    if page == "fleur.html":
        html = apply_fleur_images(html)
    elif page == "windows.html":
        html = apply_windows_gallery(html)
    return head_block(page, lang, styles) + html + "\n</body>\n</html>\n"


def apply_fleur_gallery(template: str) -> str:
    """Map FLEUR Drive WebPs onto the bundled gallery grid (production layout)."""
    gallery_imgs = "".join(
        f'<img src="{src}" alt="FLEUR — LeDockerNoir" style="width:100%;aspect-ratio:4/5;object-fit:cover;display:block">'
        for src in [f"{FLEUR_DIR}/g{i:02d}.webp" for i in range(1, 9)]
    )
    return re.sub(
        r'<div style="display:grid;grid-template-columns:repeat\(4,1fr\);gap:1px;background:rgba\(233,236,242,.12\);border-top:1px solid rgba\(233,236,242,.12\);border-bottom:1px solid rgba\(233,236,242,.12\)">\s*'
        r'(?:<img src="[^"]+" alt="FLEUR[^"]*" style="width:100%;aspect-ratio:4/5;object-fit:cover;display:block">\s*)+'
        r"</div>",
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:rgba(233,236,242,.12);border-top:1px solid rgba(233,236,242,.12);border-bottom:1px solid rgba(233,236,242,.12)">{gallery_imgs}</div>',
        template,
        count=1,
    )


def set_bundle_template(html: str, template: str) -> str:
    payload = json_for_script_embed(template)
    open_tag = '<script type="__bundler/template">'
    start = html.index(open_tag) + len(open_tag)
    end = html.rindex("</script>", start)
    return html[:start] + payload + html[end:]


def set_default_locale(template: str, lang: str) -> str:
    if lang != "en":
        return template
    template = template.replace(
        '<sc-if value="{{ isFr }}" hint-placeholder-val="{{ true }}">',
        '<sc-if value="{{ isFr }}" hint-placeholder-val="{{ false }}">',
        1,
    )
    template = template.replace(
        '<sc-if value="{{ isEn }}" hint-placeholder-val="{{ false }}">',
        '<sc-if value="{{ isEn }}" hint-placeholder-val="{{ true }}">',
        1,
    )
    return template


def fix_bundle_nav_links(template: str, lang: str) -> str:
    if lang == "fr":
        for name in PAGES:
            base = name.replace(".html", "")
            template = template.replace(f'href="{name}"', f'href="/{base}"')
        return template
    for name in PAGES:
        base = name.replace(".html", "")
        en_path = "/en/" if name == "index.html" else f"/en/{base}"
        template = template.replace(f'href="{name}"', f'href="{en_path}"')
    return template


def inject_document_seo(html: str, page: str, lang: str) -> str:
    meta = PAGE_META[page][lang]
    slug = page.replace(".html", "")
    if slug == "index":
        path = "/" if lang == "fr" else "/en/"
    else:
        path = f"/{slug}" if lang == "fr" else f"/en/{slug}"
    canonical = SITE_URL + path
    alt_fr = SITE_URL + (f"/{slug}" if slug != "index" else "/")
    alt_en = SITE_URL + (f"/en/{slug}" if slug != "index" else "/en/")
    if page == "fleur.html":
        og = FLEUR_OG
    elif page == "windows.html":
        og = WINDOWS_OG
    else:
        og = f"{SITE_URL}/assets/images/og-default.webp"
    lang_attr = "fr" if lang == "fr" else "en"
    block = f"""
  <title>{meta["title"]}</title>
  <meta name="description" content="{meta["description"]}">
  <link rel="canonical" href="{canonical}">
  <link rel="alternate" hreflang="fr" href="{alt_fr}">
  <link rel="alternate" hreflang="en" href="{alt_en}">
  <link rel="alternate" hreflang="x-default" href="{alt_fr}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Compagnie THT">
  <meta property="og:title" content="{meta["title"]}">
  <meta property="og:description" content="{meta["description"]}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{ld_json_script_tag(page, lang)}
"""
    html = re.sub(r"<title>Bundled Page</title>", block.strip(), html, count=1)
    html = re.sub(r"<html>", f'<html lang="{lang_attr}">', html, count=1)
    return html


def shrink_externalized_manifest(html: str, uuid_map: dict[str, str]) -> str:
    m = re.search(r'(<script type="__bundler/manifest">)(.*?)(</script>)', html, re.DOTALL)
    if not m:
        return html
    manifest = json.loads(m.group(2))
    for uid in uuid_map:
        entry = manifest.get(uid)
        if isinstance(entry, dict) and entry.get("mime", "").startswith("image/"):
            entry["data"] = ""
            entry["compressed"] = False
    payload = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    return html[: m.start(2)] + payload + html[m.end(2) :]


def patch_template(template: str, page: str, lang: str) -> str:
    template = fix_contact_email(template)
    template = set_default_locale(template, lang)
    template = fix_bundle_nav_links(template, lang)
    # Keep @font-face src as manifest UUIDs — the bundler split/join would break /assets/fonts/<uuid>.woff2 paths.
    template = replace_uuids(template, uuid_map_global, include_fonts=False)
    template = fix_wp_urls(template)
    template = fix_pronouns(template)
    if page == "cherche-en-corps.html":
        template = fix_cherche_title_logo(template)
        template = fix_cherche_videos(template, "fr")
        template = fix_cherche_videos(template, "en")
        template = template.replace("LgsgqCNG7_U", "")
        template = fix_dossier_links(template, page)
    if page == "contact.html":
        template = fix_dossier_links(template, page)
    if page == "fleur.html":
        template = apply_fleur_gallery(template)
    if page == "windows.html":
        template = fix_wp_urls(template)
        template = apply_windows_gallery(template)
    if page == "index.html":
        template = fix_wp_urls(template)
        template = fix_newsletter(template, "fr")
        template = fix_newsletter(template, "en")
        template = template.replace(
            "https://www.youtube.com/watch?v=K9OICzieSfc",
            "https://www.youtube.com/watch?v=TjewwAOC488",
        )
        template = template.replace(
            "▶ Cherche en Corps à San Francisco",
            "▶ Cherche en Corps — teaser",
        )
        template = template.replace(
            "▶ Cherche en Corps in San Francisco",
            "▶ Cherche en Corps — teaser",
        )
    return template


uuid_map_global: dict[str, str] = {}


def patch_bundle(html: str, page: str, lang: str) -> str:
    html = fix_contact_email(html)
    _manifest, template = parse_bundle(html)
    template = patch_template(template, page, lang)
    html = set_bundle_template(html, template)
    # Never replace_uuids/fix_wp_urls on the full document — that corrupts manifest JSON keys.
    html = inject_document_seo(html, page, lang)
    return html


def write_sitemap() -> None:
    urls = []
    for page in PAGES:
        slug = page.replace(".html", "")
        for lang in ("fr", "en"):
            if slug == "index":
                path = "/" if lang == "fr" else "/en/"
            else:
                path = f"/{slug}" if lang == "fr" else f"/en/{slug}"
            urls.append(f"  <url><loc>{SITE_URL}{path}</loc></url>")
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    (OUT / "sitemap.xml").write_text(content, encoding="utf-8")


def write_robots() -> None:
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def write_llms_txt() -> None:
    fr = f"""# Compagnie THT (Trois Heures Trente)

> Compagnie de danse hip-hop et contemporaine, basée à Carrières-sous-Poissy (France) et Oslo (Norvège).

Contact: {CONTACT_EMAIL}
Site: {SITE_URL}

## Créations

- [FLEUR]({SITE_URL}/fleur): solo hip-hop de Ouili Nana, 50 minutes.
- [Cherche en Corps]({SITE_URL}/cherche-en-corps): duo de Ouili Nana et Raphaël Saint-Laurent, 50 minutes. Teaser: {CHERCHE_TEASER_URL}
- [WINDOWS]({SITE_URL}/windows): création 2025, chorégraphie Ouili Nana, trio hip-hop.

## Pages

- [Accueil]({SITE_URL}/)
- [Ateliers]({SITE_URL}/ateliers)
- [Contact]({SITE_URL}/contact)

## English

- [Home]({SITE_URL}/en/)
- [Workshops]({SITE_URL}/en/ateliers)
- [Contact]({SITE_URL}/en/contact)
- [FLEUR]({SITE_URL}/en/fleur)
- [Cherche en Corps]({SITE_URL}/en/cherche-en-corps)
- [WINDOWS]({SITE_URL}/en/windows)
"""
    en = f"""# THT Company (Trois Heures Trente)

> Hip-hop and contemporary dance company based in Carrières-sous-Poissy, France and Oslo, Norway.

Contact: {CONTACT_EMAIL}
Website: {SITE_URL}

## Works

- [FLEUR]({SITE_URL}/en/fleur): hip-hop solo by Ouili Nana, 50 minutes.
- [Cherche en Corps]({SITE_URL}/en/cherche-en-corps): duo by Ouili Nana and Raphaël Saint-Laurent, 50 minutes. Teaser: {CHERCHE_TEASER_URL}
- [WINDOWS]({SITE_URL}/en/windows): 2025 creation choreographed by Ouili Nana, hip-hop trio.

## Pages

- [Home]({SITE_URL}/en/)
- [Workshops]({SITE_URL}/en/ateliers)
- [Contact]({SITE_URL}/en/contact)

## Français

- [Accueil]({SITE_URL}/)
"""
    (OUT / "llms.txt").write_text(fr, encoding="utf-8")
    en_dir = OUT / "en"
    en_dir.mkdir(exist_ok=True)
    (en_dir / "llms.txt").write_text(en, encoding="utf-8")


def main() -> int:
    global uuid_map_global
    LEGACY.mkdir(parents=True, exist_ok=True)
    missing = [p for p in PAGES if not (LEGACY / p).exists()]
    if missing:
        print(
            "Missing legacy bundles (restore from main): " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    ensure_cherche_logo_asset()
    uuid_map_global = collect_assets()

    og = ASSETS / "images" / "og-default.webp"
    if not og.exists():
        hero_candidates = list((ASSETS / "images" / "windows").glob("hero.webp"))
        if hero_candidates:
            shutil.copy2(hero_candidates[0], og)

    en_dir = OUT / "en"
    en_dir.mkdir(exist_ok=True)
    for page in PAGES:
        raw = (LEGACY / page).read_text(encoding="utf-8")
        (OUT / page).write_text(patch_bundle(raw, page, "fr"), encoding="utf-8")
        en_name = "index.html" if page == "index.html" else page
        (en_dir / en_name).write_text(patch_bundle(raw, page, "en"), encoding="utf-8")

    write_sitemap()
    write_robots()
    write_llms_txt()

    raw_dir = ASSETS / "_raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)

    print("Patched bundled pages.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
