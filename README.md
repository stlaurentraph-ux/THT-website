# THT website

Production design is the **Claude artifact bundles** (same as [trois-heures-trente.com](https://trois-heures-trente.com)). This repo patches those bundles for SEO, assets, Cherche videos, newsletter, and `/en` URLs — without replacing the React layout.

## Pages

| URL (FR) | URL (EN) | Source |
| --- | --- | --- |
| `/` | `/en/` | `index.html`, `en/index.html` |
| `/ateliers` | `/en/ateliers` | bundled + patched |
| `/cherche-en-corps` | `/en/cherche-en-corps` | … |
| `/contact` | `/en/contact` | … |
| `/fleur` | `/en/fleur` | … |
| `/windows` | `/en/windows` | … |

Caddy `try_files` maps extensionless paths to `.html`.

## Build (patch bundles)

Canonical bundles live in `legacy/bundles/` (from `main`). Regenerate deployable HTML:

```sh
pip install pillow
python3 scripts/build_site.py
```

This externalizes images/fonts to `assets/`, applies agreed content fixes inside the bundled template, writes FR root + `en/` copies (English default locale), and updates `sitemap.xml`, `robots.txt`, and `llms.txt`.

Public contact email: `compagnie.tht@gmail.com`.

## Newsletter API

Home newsletter block posts to `POST /api/subscribe`. Docker runs Caddy + Python API on `127.0.0.1:8000`.

See `.env.example` for Notion + Infomaniak SMTP variables.

## Deploy

Railway builds the `Dockerfile` (Caddy on `$PORT`, static `/srv`, `/api/*` proxied).

## Visual regression

```sh
python3 -m http.server 8080   # local patched site (*.html paths)
python3 scripts/capture_compare.py   # production vs local side-by-sides → /opt/cursor/artifacts/compare/
```
