# CONTEXT — handoff

_Last updated: 2026-10-14 (**session 10**). Companions: `GOAL.md` (north star), `TASKs.md` (ledger)._

---

## 1. North star
POSSE — write once on the blog (canonical) → publish → fan out to the chosen socials → each social post
carries the blog URL → the post shows where it was syndicated ("Also published on…").

**Stack:** Flask + MongoDB via **MongoEngine** + a **local/cloud storage-provider layer** + a Cloudflare
**named tunnel**.

---

## 2. Where we are (session 10)
- **Syndication live:** LinkedIn (native, **personal profile**, refreshable token), Facebook / Instagram /
  Bluesky / Pinterest, and **YouTube** (video + the full upload metadata, via SocialAPI). **Medium** via its
  importer. **X** short-post-only; **Threads** not pursued.
- **"Also published on"** row renders on every card + post/article page — posted platforms active, others
  dimmed; failed attempts show retry banners (logged-in).
- **ORM enforced:** all DB access through MongoEngine Documents in `src/db/` (`Post`/`Comment`/
  `AnalyticsEvent`; `syndications` declared). No file store (`blog.json`, `sync_storage`, `dbinit` gone);
  a local or Atlas `mongod` is supported.
- **Storage is provider-agnostic & cloud-migrated:** `src/providers/` — a **`local`/`cloud` selector per data type**
  (`DEFAULT_BACKEND` + `MEDIA_BACKEND`/`DB_BACKEND`); Cloudflare R2 SigV4 adapter (`src/providers/cloud/r2.py`, zero AWS SDK dependencies);
  database supports distinct `LOCAL_MONGO_URI` and `ATLAS_MONGO_URI` with auto-switch logic (`dc61b13`).
- **Render Ready:** `render.yaml` configured with production settings and Gunicorn workers.
- **Stateless Persistence:** LinkedIn OAuth tokens persist in MongoDB (`secrets` collection) with file fallback so tokens survive container redeploys.
- **Thin `app.py`** (~607 lines): Flask init + 25 route view functions + `app.run`; all logic lives in
  `src/` packages.
- **Tunnel:** the auto-start `cloudflared` Windows service routes `blog.potluri-krishna-priyatham.tech` →
  `127.0.0.1:5000`. Trial domain good for **≥1 year**; permanent `://kittupriyatham.com` planned.
- **Repo tidy:** session notes in `.ai_docs/`; README images in `static/images/readme/`; runtime in `data/`.
- **Commits:** sessions 6–9 committed up to baseline `f6067e5`. Session 10 migration committed in `e7fe968`, docs synced in `0f370a9`, dual URI support in `dc61b13`, and diagram updated in `96627f4`.

---

## 3. Layout

```text
app.py                       # Flask init + routes + app.run  (thin)
render.yaml                  # Render service blueprint
scripts/
  migrate_to_atlas.py        # One-off migration (local Mongo + media -> Atlas + R2)
src/
  __init__.py                # regular package marker
  config/    settings.py     # env + constants (LOCAL_MONGO_URI, ATLAS_MONGO_URI, R2)
  providers/ base.py registry.py local.py cloud/{media,mongo,http,r2}.py   # local vs cloud storage per data type
  media/     uploads.py paths.py
  content/   rich_text.py helpers.py urls.py
  analytics/ events.py reports.py
  notify/    telegram.py
  syndication/ base.py socialapi.py socialapi_metrics.py linkedin.py linkedin_token.py linkedin_metrics.py imageprep.py rewrite.py textcard.py runner.py
  db/        models.py + __init__.py (connect_db, ensure_schema)
templates/  static/  media/  data/  .ai_docs/
```

---

## 4. What happened (sessions 6–10)
- **6** — fixed the "Also published on" row; enforced the MongoEngine ORM; removed the file store; root
  cleanup; README revamp; tunnel fixed as an auto-start **boot service**; **`app.py` refactored** thin.
- **7** — **cloud data-layer abstraction** (the providers layer); **rigorous test pass** (51/53) + fixes
  (stale Azure refs, provider error contract, orphaned draft status); `/posts`+`/articles` confirmed
  intentionally public.
- **8** — **LinkedIn refresh-token flow** (`src/syndication/linkedin_token.py`, wired + documented;
  backward compatible); **free dry-run Validate** (all SocialAPI platforms valid); **Medium import**
  verified as-is.
- **9** — **analytics dashboard** (per-post × per-platform via `socialapi_metrics.py`/`linkedin_metrics.py`,
  beside first-party blog events); **editor** rebuild (live per-platform text preview, 14 rich blocks,
  attachment remove/reorder); **YouTube** page + upload metadata; **LinkedIn posts as the personal profile**
  (member metrics proven API-gated — `403 partnerApi…` — and the SocialAPI read path staged, inactive);
  **stale `SITE_URL` fixed** in `settings.py`. Session 9 closed out cleanly to establish the code-commit baseline.
- **10** — **Cloud migration to Render + MongoDB Atlas + Cloudflare R2**:
  - Implemented `src/providers/cloud/r2.py` (zero-SDK SigV4 S3 adapter for Cloudflare R2).
  - Moved LinkedIn token store to MongoDB (`secrets` collection) with file fallback.
  - Added `render.yaml` blueprint with health check and environment bindings.
  - Implemented `scripts/migrate_to_atlas.py` for DB collection & media asset migration.
  - Added `LOCAL_MONGO_URI` and `ATLAS_MONGO_URI` with auto-switching logic and comment-safe env reading (`dc61b13`).
  - Synced local `.env` with updated template and configured live `ATLAS_MONGO_URI` connection string.

---

## 5. Gotchas (read before debugging)
- **MongoEngine:** `Model(**unknown_kwarg)` raises `FieldDoesNotExist` even with `strict=False` — pass only
  declared fields (or insert via the model's raw collection).
- **`SITE_URL` prefers `.env`** — `src/config/settings.py` reads the `.env` value and writes it back into
  `os.environ`, so a stale OS-level `SITE_URL` can no longer shadow it (fixed in session 9). Editing `.env` is
  enough to move domains.
- **MongoDB URI precedence:** `MONGO_URI` takes priority. If empty, automatically selects `ATLAS_MONGO_URI` when `DB_BACKEND=cloud` (or `DEFAULT_BACKEND=cloud`), and `LOCAL_MONGO_URI` when local.
- `src/` is a **regular** package (has `__init__.py`); no loose `.py` directly under `src/`.
- Admin *areas* need login — **except `/posts` and `/articles`, which are intentionally PUBLIC** (a
  social-style feed, like LinkedIn/Facebook; only drafts are gated). **Not an auth bug.**
- **Only one Flask instance per port.**
- `data/` holds runtime state — `analytics.jsonl`, `medium_auth.json`, `linkedin_token.json` (git-ignored,
  never web-served).

---

## 6. Open items / next
- **LinkedIn engagement** — blocked on SocialAPI's reply (`TASKs.md` #1); the read path is staged.
- **Deploy live on Render & run Atlas/R2 migration script** — With code completed and committed, run `scripts/migrate_to_atlas.py` once Atlas & R2 credentials are plugged into `.env`, and link repository to Render.
- **YouTube end-to-end** — built but not yet exercised with a real video (spends a SocialAPI credit).
- **Permanent domain**; hand-written per-platform overrides; scheduling; metrics read-back; expand the Attach menu.
- **SocialAPI quota** = 10 posts/month (validate is free) — confirm whether a multi-platform post spends one
  credit or one per platform.