# TASKs

Ordered ledger. Companions: `GOAL.md` (why), `CONTEXT.md` (where we are).
**Initial foundation changes are committed up to commit f6067e5. The cloud migration items and dual MongoDB URI support are committed in commits e7fe968, 0f370a9, and dc61b13 for Session 10.**

---

## Start here (session 12: Error Handling, Uptime, SEO & AI Context)

### Session 12 Implementation Checklist

| # | Component Task Target | Scope / Specification | Status |
|:---|:---|:---|:---:|
| 1.1 | **Dynamic Public Error Template** | Create `templates/error.html` styled with dark palette, dynamic `error_code`, `error_title`, `error_message`, and home feed return button | ✅ Completed |
| 1.2 | **Global Error Handlers** | Register `@app.errorhandler(404)`, `403`, and `500` in `app.py` returning `templates/error.html` | ✅ Completed |
| 1.3 | **Static Admin Decoy 404** | Create `templates/admin_not_found.html` with raw, unstyled Apache/Nginx generic browser 404 text (zero branding/scripts/links) | ✅ Completed |
| 1.4 | **Edge Admin Decoy Interception** | In `@app.before_request`, intercept unauthorized requests to admin paths (`/login`, `/analytics`, `/admin/*`, editors) with `admin_not_found.html` (404) | ✅ Completed |
| 2.1 | **Lightweight `/health` Endpoint** | Implement `@app.route('/health')` returning plain text `OK` (200) without database connection, storage access, or template rendering | ✅ Completed |
| 3.1 | **Anti-Indexing `X-Robots-Tag` Hook** | In `@app.after_request`, inject `X-Robots-Tag: noindex, nofollow, noarchive, nosnippet` on private/admin routes and error responses | ✅ Completed |
| 3.2 | **Standard `robots.txt`** | Implement `@app.route('/robots.txt')` allowing public feeds and `/llms.txt`, disallowing admin paths, referencing dynamic `Sitemap:` URL | ✅ Completed |
| 3.3 | **Dynamic XML Sitemap Engine** | Implement `@app.route('/sitemap.xml')` (schema 0.9) querying published posts/articles with `<loc>` and ISO `<lastmod>` | ✅ Completed |
| 4.1 | **AI Context Feed (`/llms.txt`)** | Implement `@app.route('/llms.txt')` outputting structured markdown catalog of posts/articles for LLMs & AI agents | ✅ Completed |
| 5.1 | **Horizontal More Options (`...`) Menu** | Add horizontal `...` button menu with Edit & Delete for published items, and Delete for drafts across feeds (`/`, `/posts`, `/articles`) and detail views (`/post/<id>`, `/article/<id>`) | ✅ Completed |

---

### Retained & Deferred (Do Later)
- **Multi-user system**: Deferred for future multi-author expansion.
- **Permanent domain (`kittupriyatham.com`)**: Retained until purchased and DNS configured.
- **LinkedIn engagement**: Awaiting SocialAPI partner beta reply.
- **YouTube end-to-end**: Exercise with real video upload.

### Struck Off / Dropped
- **Scheduling (`scheduled_at`)**: Dropped (immediate publication preferred).
- **Threads syndication**: Dropped.

---

## Done (session 11)

### Stealth Admin Hardening, Documentation Revamp & Medium POSSE

| Item | Component Task Target | Status |
|:---|:---|:---:|
| 1 | Implemented HMAC-SHA256 persistent device authorization cookie (`admin_device_token`) | ✅ Verified live |
| 2 | Enforce 404 on `/login`, `/posts` drafts, and `/articles` drafts for unauthorized devices | ✅ Verified live |
| 3 | Hide Admin button on `/` and Draft tabs on feeds from DOM for unauthenticated public readers | ✅ Verified live |
| 4 | Fixed Render reverse-proxy loopback flaw (`remote_addr == '127.0.0.1'`) in `app.py` | ✅ Verified live |
| 5 | Complete `README.md` revamp with full replication guide, local vs. cloud `.env`, and stealth docs | ✅ Completed |
| 6 | Fixed relative image references in `README.md` (`./static/images/readme/<file>`) | ✅ Completed |
| 7 | Built & verified Violentmonkey userscript v1.1.0 (`p/import` auto-fill + `new-story` auto-paste) | ✅ Verified live |
| 8 | Updated post and article template buttons with `openMediumImporter()` fallback bridge | ✅ Verified live |
| 9 | Retired local `data/medium_auth.json` and Atlas `medium_auth` secret document | ✅ Completed |

---

## Done (session 10)

### Cloud Migration Architecture & Verification

| Item | Component Task Target | Status |
|:---|:---|:---:|
| 1 | Create `core/providers/cloud/r2.py` — SigV4 upload adapter (stdlib only) | ✅ Completed (`e7fe968`) |
| 2 | Add R2 env vars to `core/config/settings.py` and re-export from `core/config/__init__.py` | ✅ Completed (`e7fe968`) |
| 3 | Move LinkedIn OAuth token store to Mongo in `core/syndication/linkedin_token.py` | ✅ Completed (`e7fe968`) |
| 4 | Create `render.yaml` blueprint with all keys syncing from file | ✅ Completed (`e7fe968`) |
| 5 | Document the R2 block in `.env.example` | ✅ Completed (`e7fe968`) |
| 6 | Write `scripts/migrate_to_atlas.py` (posts/comments/analytics, LinkedIn token, media) | ✅ Completed (`e7fe968`) |
| 7 | Add dual `LOCAL_MONGO_URI` and `ATLAS_MONGO_URI` with auto-switch | ✅ Completed (`dc61b13`) |
| 8 | Update local `.env` with new schema and live `ATLAS_MONGO_URI` credentials | ✅ Completed |
| 9 | Verify: import the app, run a local smoke test, confirm no regressions | ✅ Verified (all tests pass) |

---

## Done (session 9)

- **LinkedIn posts as the personal profile** — `LINKEDIN_ORGANIZATION_URN` blanked; `author_urn()` resolves to the member URN; the token store was re-minted with `w_member_social` **and** the org scopes. Verified: post author, `is_configured`, 30 routes.
- **LinkedIn *member* metrics are API-gated (proven live)** — `memberCreatorPostAnalytics` and `socialActions` both return `403 partnerApi…`; they need `r_member_postAnalytics` = the Community Management API.
- **SocialAPI LinkedIn metrics path staged (inactive)** — `socialapi_metrics.SOCIALAPI_METRIC_PLATFORMS` (empty today) routes a *natively-published* platform's metrics to SocialAPI; `socialapi.py` records that LinkedIn is deliberately not a SocialAPI publishing platform.
- **YouTube video path built** — a dedicated `/youtube/<post_id>` page (+ an inline composer panel) collects the full upload metadata into `doc["youtube"]`; the SocialAPI adapter sends it as the `platform_data.youtube` block.
- **Per-platform text — rigorously tested, no bugs** — 100+ checks: per-platform limits, link suffix, exact-fit vs over-limit boundaries, per-platform independence, empty body, article-vs-post, CRLF, non-public URL, `_preview_shortened` mirroring `compose_text`, and `/api/syndication/preview`.
- **Stale `SITE_URL` fixed in code** — `core/config/settings.py` now prefers the `.env` value for `SITE_URL` and writes it back into `os.environ`.
- **Analytics + editor (built earlier this session)** — per-post × per-platform social metrics + first-party blog analytics; the editor gained per-platform preview, 14 rich blocks, attachment remove/reorder.

---

## Done (session 8)

- **LinkedIn refresh-token flow** — `core/syndication/linkedin_token.py` wired into `linkedin.py` (all 4 token reads). `.env.example` documents `LINKEDIN_CLIENT_ID`/`LINKEDIN_CLIENT_SECRET`/`LINKEDIN_REDIRECT_URI` + the setup CLI.
- **Free dry-run Validate** on `welcome_post` → facebook/instagram/youtube/bluesky/pinterest all `valid` (bluesky warns 282/300); linkedin has no dry-run.
- **Medium import** verified as-is (copies the canonical URL + opens `://medium.com`).
- **Rigorous full-project test pass** (51/53) — fixed stale Azure references, the cloud provider `exists()/delete()` error contract, and an orphaned draft's status.

---

## Done (session 7)

- **Cloud data-layer abstraction** — a `local`/`cloud` selector per data type (media, database) with pluggable adapters, wired behind `media.*` / `db.*`. Azure removed.

---

## Done (session 6) — committed + pushed

- Fixed the **"Also published on"** row; **enforced the MongoEngine ORM**; removed the file store; **root cleanup** (`.ai_docs/`, `static/images/readme/`, `data/`); **README revamp**; tunnel as an auto-start **boot service**; **`app.py` refactored** to routes + init + run.