# CONTEXT — handoff

_Last updated: 2026-10-01 (**session 8**). Companions: `GOAL.md` (north star), `TASKs.md` (ledger)._

---

## 1. North star
POSSE — write once on the blog (canonical) → publish → fan out to the chosen socials → each social post
carries the blog URL → the post shows where it was syndicated ("Also published on…").

**Stack:** Flask + MongoDB via **MongoEngine** + a **local/cloud storage-provider layer** + a Cloudflare
**named tunnel**.

---

## 2. Where we are (end of session 8)
- **Syndication live:** LinkedIn (native — now with a **refreshable token**), Facebook / Instagram / Bluesky
  / Pinterest (SocialAPI). **YouTube** needs a real video + metadata (design ready, not built). **Medium**
  via its importer. **X / Threads** not pursued.
- **"Also published on"** row renders on every card + post/article page — posted platforms active, others
  dimmed; failed attempts show retry banners (logged-in).
- **ORM enforced:** all DB access through MongoEngine Documents in `src/db/` (`Post`/`Comment`/
  `AnalyticsEvent`; `syndications` declared). No file store (`blog.json`, `sync_storage`, `dbinit` gone);
  a local `mongod` is required.
- **Storage is provider-agnostic:** `src/providers/` — a **`local`/`cloud` selector per data type**
  (`DEFAULT_BACKEND` + `MEDIA_BACKEND`/`DB_BACKEND`); cloud media reaches the platform via a **plug-in HTTP
  upload adapter** (`register_adapter`, **no cloud SDK**); cloud database = any MongoDB-compatible URL.
  Azure removed.
- **Thin `app.py`** (~607 lines): Flask init + 25 route view functions + `app.run`; all logic lives in
  `src/` packages.
- **Tunnel:** the auto-start `cloudflared` Windows service routes `blog.potluri-krishna-priyatham.tech` →
  `127.0.0.1:5000`. Trial domain good for **≥1 year**; permanent `blog.kittupriyatham.com` planned.
- **Repo tidy:** session notes in `.ai_docs/`; README images in `static/images/readme/`; runtime in `data/`.
- **Commits:** sessions 6–8 are committed and pushed.

---

## 3. Layout
```
app.py                       # Flask init + routes + app.run  (thin)
src/
  __init__.py                # regular package marker
  config/    settings.py     # env + constants
  providers/ base.py registry.py local.py cloud/{media,mongo,http}.py   # local vs cloud storage per data type
  media/     uploads.py paths.py
  content/   rich_text.py helpers.py urls.py
  analytics/ events.py reports.py
  notify/    telegram.py
  syndication/ base.py socialapi.py linkedin.py linkedin_token.py imageprep.py rewrite.py textcard.py runner.py
  db/        models.py + __init__.py (connect_db, ensure_schema)
templates/  static/  media/  data/  .ai_docs/
```

---

## 4. What happened (sessions 6–8)
- **6** — fixed the "Also published on" row; enforced the MongoEngine ORM; removed the file store; root
  cleanup; README revamp; tunnel fixed as an auto-start **boot service**; **`app.py` refactored** thin.
- **7** — **cloud data-layer abstraction** (the providers layer); **rigorous test pass** (51/53) + fixes
  (stale Azure refs, provider error contract, orphaned draft status); `/posts`+`/articles` confirmed
  intentionally public.
- **8** — **LinkedIn refresh-token flow** (`src/syndication/linkedin_token.py`, wired + documented;
  backward compatible); **free dry-run Validate** (all SocialAPI platforms valid); **Medium import**
  verified as-is.

---

## 5. Gotchas (read before debugging)
- **MongoEngine:** `Model(**unknown_kwarg)` raises `FieldDoesNotExist` even with `strict=False` — pass only
  declared fields (or insert via the model's raw collection).
- **`SITE_URL` in the OS env beats `.env`** (`load_dotenv` doesn't override) — clear a stale `$env:SITE_URL`
  if the public URL looks wrong.
- `src/` is a **regular** package (has `__init__.py`); no loose `.py` directly under `src/`.
- Admin *areas* need login — **except `/posts` and `/articles`, which are intentionally PUBLIC** (a
  social-style feed, like LinkedIn/Facebook; only drafts are gated). **Not an auth bug.**
- **Only one Flask instance per port.**
- `data/` holds runtime state — `analytics.jsonl`, `medium_auth.json`, `linkedin_token.json` (git-ignored,
  never web-served).

---

## 6. Open items / next
- **Commit** the session-8 LinkedIn-flow change.
- **YouTube** video path (see `TASKs.md` for the design).
- **Permanent domain**; per-platform text overrides; scheduling; metrics read-back; expand the Attach menu.
- **SocialAPI quota** = 10 posts/month (validate is free).
