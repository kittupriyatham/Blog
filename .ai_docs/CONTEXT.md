# CONTEXT — handoff

_Last updated: 2026-10-17 (**session 11**). Companions: `GOAL.md` (north star), `TASKs.md` (ledger)._

---

## 1. North star
POSSE — write once on the blog (canonical) → publish → fan out to the chosen socials → each social post
carries the blog URL → the post shows where it was syndicated ("Also published on…").

**Stack:** Flask + MongoDB via **MongoEngine** + a **local/cloud storage-provider layer** + a Cloudflare
**named tunnel** or **Render Web Service** behind Cloudflare DNS/WAF.

---

## 2. Where we are (session 11)
- **Stealth Admin & Drafts Lockdown (Live & Verified):**
  - Public readers and untrusted devices receive a clean `404 Not Found` when trying to browse `/login` or unpublished drafts.
  - The "Admin" navigation button on `/` and the "Draft" tabs on `/posts` and `/articles` are hidden unless authenticated via client certificate or authorized hardware device token.
  - Implemented cryptographic HMAC-SHA256 device recognition (`admin_device_token` cookie based on `SECRET_KEY` + `ADMIN_USERNAME`) so the author's primary hardware retains persistent stealth access without leaking the portal to public users.
  - Fixed reverse-proxy loopback trap in `app.py`: Gunicorn behind Render sets `request.remote_addr == '127.0.0.1'`, which previously bypassed authorization for all external users; loopback bypass removed in favor of strict HMAC / certificate checks.
- **Medium Syndication via Violentmonkey (Verified & Operational):**
  - Fully integrated with [`static/js/medium_posse_userscript.user.js`](./static/js/medium_posse_userscript.user.js) (`v1.1.0`), supporting dual pathways:
    1. **Medium URL Importer (`/p/import`)**: Copies canonical URL to clipboard and passes payload via `window.name` to auto-fill the import field.
    2. **Rich Story Bridge (`/new-story`)**: Admin click parses article DOM, resolves relative assets, attaches canonical attribution, and auto-pastes directly into Medium's editor.
  - Deprecated and removed legacy `data/medium_auth.json` and Atlas `medium_auth` secret document.
- **Documentation & Replication Revamp:**
  - `README.md` completely updated with a step-by-step replication guide from scratch, distinct local vs. Render cloud `.env` configuration blocks, fixed screenshot asset paths (`./static/images/readme/<file>`), Violentmonkey installation guide, and an optional stealth admin hardening guide.
- **ORM enforced & Storage Cloud-Ready:**
  - All DB access through MongoEngine in `core/db/`.
  - Cloudflare R2 SigV4 adapter (`core/providers/cloud/r2.py`) and Atlas migration script (`scripts/migrate_to_atlas.py`) fully verified and operational.
  - Render deployment blueprint (`render.yaml`) verified.
- **Commits & Deployments:**
  - Session 11 completed, verified in production on `https://blog.potluri-krishna-priyatham.tech`, and finalized for push.

---

## 3. Layout

```text
app.py                       # Flask init + routes + stealth auth + app.run  (thin)
render.yaml                  # Render service blueprint
README.md                    # Complete setup, replication guide & stealth docs
scripts/
  migrate_to_atlas.py        # Migration tool (local Mongo + media -> Atlas + R2)
core/
  __init__.py                # regular package marker
  config/    settings.py     # env + constants (LOCAL_MONGO_URI, ATLAS_MONGO_URI, R2)
  providers/ base.py registry.py local.py cloud/{media,mongo,http,r2}.py   # local vs cloud storage
  media/     uploads.py paths.py
  content/   rich_text.py helpers.py urls.py
  analytics/ events.py reports.py
  notify/    telegram.py
  syndication/ base.py socialapi.py socialapi_metrics.py linkedin.py linkedin_token.py linkedin_metrics.py imageprep.py rewrite.py textcard.py runner.py
  db/        models.py + __init__.py (connect_db, ensure_schema)
templates/  static/  media/  data/  .ai_docs/
```

---

## 4. What happened (sessions 6–11)
- **6** — fixed the "Also published on" row; enforced the MongoEngine ORM; removed the file store; root
  cleanup; README revamp; tunnel fixed as an auto-start **boot service**; **`app.py` refactored** thin.
- **7** — **cloud data-layer abstraction** (the providers layer); **rigorous test pass** (51/53) + fixes
  (stale Azure refs, provider error contract, orphaned draft status); `/posts`+`/articles` confirmed
  intentionally public.
- **8** — **LinkedIn refresh-token flow** (`core/syndication/linkedin_token.py`, wired + documented;
  backward compatible); **free dry-run Validate** (all SocialAPI platforms valid); **Medium import**
  verified as-is.
- **9** — **analytics dashboard**; **editor** rebuild; **YouTube** page + upload metadata; **LinkedIn posts as the personal profile**; **stale `SITE_URL` fixed**.
- **10** — **Cloud migration to Render + MongoDB Atlas + Cloudflare R2**:
  - Implemented `core/providers/cloud/r2.py` (SigV4 S3 adapter).
  - Moved LinkedIn token store to MongoDB (`secrets` collection) with file fallback.
  - Added `render.yaml` blueprint.
  - Implemented `scripts/migrate_to_atlas.py` for DB collection & media asset migration.
  - Added `LOCAL_MONGO_URI` and `ATLAS_MONGO_URI` with auto-switching logic.
- **11** — **Stealth Admin Lockdown & Complete Replication Documentation**:
  - Implemented HMAC-SHA256 device recognition cookie (`admin_device_token`) with 10-year persistence for author devices.
  - Hardened `/login`, draft views, and navigation: unknown devices get 404 and draft toggles are omitted from DOM.
  - Eliminated reverse-proxy `request.remote_addr == '127.0.0.1'` bypass that leaked admin routes on Render container deployments.
  - Updated `README.md` with complete replication instructions, local vs. cloud `.env` templates, resolved broken screenshot paths, and stealth admin setup notes.
  - Cleaned up runtime authentication plan (deprecated `medium_auth.json` in favor of Violentmonkey importer).

---

## 5. Gotchas (read before debugging)
- **Cloudflare Edge mTLS vs. Origin:** Cloudflare terminates TLS at its edge and strips client certificates before hitting the origin. If passing verification to origin, Cloudflare Transform Rules must set a custom header like `X-Client-Cert-Verified: true` (Cloudflare blocks setting `cf-*` headers via Transform Rules).
- **Stealth 404 Access:** If accessing `/login` on a new authorized hardware device, author must either authenticate through Cloudflare mTLS or set the HMAC-SHA256 signature cookie. Once logged in, the 10-year device token cookie is minted automatically.
- **MongoEngine:** `Model(**unknown_kwarg)` raises `FieldDoesNotExist` even with `strict=False` — pass only declared fields.
- **MongoDB URI precedence:** `MONGO_URI` takes priority. If empty, automatically selects `ATLAS_MONGO_URI` when `DB_BACKEND=cloud` (or `DEFAULT_BACKEND=cloud`), and `LOCAL_MONGO_URI` when local.
- **Medium Syndication:** Medium uses Violentmonkey userscript and the Medium URL Importer (`medium.com/p/import`). No `medium_auth.json` required.

---

## 6. Open items / next (Session 12 Active Sprint)
- **Error Handling & Admin Decoy**: Implement `templates/error.html`, `templates/admin_not_found.html`, and `@app.before_request` decoy interception.
- **Uptime Health Check**: Deploy isolated `@app.route('/health')` (200 OK text/plain) for cold-start prevention.
- **SEO & Anti-Indexing Suite**: Add dynamic `robots.txt`, dynamic XML `sitemap.xml`, and `@app.after_request` `X-Robots-Tag: noindex, nofollow, noarchive` on private routes.
- **AI Context Feed**: Deploy `/llms.txt` adhering to llmstxt.org specification.
- **LinkedIn engagement & YouTube end-to-end**: Pending external SocialAPI beta response and real video test.