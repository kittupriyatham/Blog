# CONTEXT — handoff

_Last updated: 2026-09-30 (**session 6**). Companions: `GOAL.md` (north star), `TASKs.md` (ledger)._

---

## 1. North star
POSSE — write once on the blog (canonical) → publish → fan out to the chosen socials → each social post
carries the blog URL → the post shows where it was syndicated ("Also published on…").

**Stack:** Flask + MongoDB via **MongoEngine** + local `media/` (or Azure Blob) · templates `templates/`,
JS `static/js/` · Windows · public via a **Cloudflare named tunnel**.

---

## 2. Where we are (end of session 6)
- **Syndication live:** LinkedIn (native), Facebook / Instagram / Bluesky / Pinterest (SocialAPI).
  YouTube needs video; Medium via its importer; X / Threads pending.
- **"Also published on" row** renders on the feed cards and on post/article pages — and it is **always
  visible**: posted platforms are active links, everything else is dimmed (0 highlighted = nothing
  syndicated yet); failed attempts show retry banners for a logged-in admin.
- **ORM enforced:** all DB access goes through MongoEngine Documents in `src/db/` (`Post`, `Comment`,
  `AnalyticsEvent`; `syndications` is a declared `ListField`). `connect_db()` + `ensure_schema()` replace
  the old `dbinit.py`. A local `mongod` is required (`MONGO_URI`, else `mongodb://127.0.0.1:27017/blog_db`);
  **`mongomock` is gone** — MongoEngine cannot drive it.
- **Thin `app.py`** (605 lines): Flask init + the 25 route view functions + `app.run`. Every non-route
  function and all env config now live in packages under `src/`.
- **No file store:** `blog.json`, `sync_storage.py`, `src/storage/`, `dbinit.py` are **removed** — content
  lives only in MongoDB.
- **Runtime data** lives in `data/` (git-ignored, never web-served): `analytics.jsonl` (file analytics
  store) and `medium_auth.json` (Medium Playwright session state).
- **Tunnel:** the `cloudflared` Windows service (AUTO_START, LocalSystem) runs
  `--config %USERPROFILE%\.cloudflared\blog-config.yml tunnel run blog`, routing
  `blog.potluri-krishna-priyatham.tech → 127.0.0.1:5000`. It starts at **boot**; the URL returns 200.
  The trial domain is good for **≥1 year**; a permanent `blog.kittupriyatham.com` (via `kittupriyatham.com`)
  will take over before then.
- **Content is placeholder:** the posts/articles currently in the DB are test data — real content lands
  when the blog is actually hosted, so nothing is final (the old "dead link" concern resolves itself).
- **Repo tidy:** session notes in `.ai_docs/`; README screenshots in `static/images/readme/`; README
  revamped with a gallery.
- **Uncommitted** — the working tree holds a large diff.

---

## 3. Layout
```
app.py                       # Flask init + routes + app.run  (thin)
src/
  __init__.py                # package marker (keeps src a regular package)
  config/    settings.py     # env + constants (ROOT-relative paths)
  media/     uploads.py paths.py
  content/   rich_text.py helpers.py urls.py
  analytics/ events.py reports.py
  notify/    telegram.py
  syndication/ base.py socialapi.py linkedin.py imageprep.py rewrite.py textcard.py runner.py
  db/        models.py + __init__.py (connect_db, ensure_schema)
templates/  static/  media/  data/  .ai_docs/
```

---

## 4. What happened this session (6)
1. **Fixed the "Also published on" display.** Root cause: `_social_icons.html` gated the whole row on
   `{% if _posted %}` (≥1 posted), so a post with only *failed* attempts rendered nothing. The row now
   always renders.
2. **Enforced the ORM.** `app.py` moved onto `Post`/`Comment`/`AnalyticsEvent`; fixed a wrong-database bug
   (`MONGO_URI` without a db defaulted to the empty `mongoengine` db → now forces `blog_db`); resolved an
   index-name collision (`post_id` unique **non-sparse**).
3. **Removed the file store** (`blog.json`, `sync_storage.py`, `src/storage/`, `dbinit.py`).
4. **Root cleanup** — removed `.gitkeep`, `blog.json`, the stray root files, the screenshot, and the two
   runtime files; moved notes → `.ai_docs/`, README images → `static/images/readme/`, runtime → `data/`.
5. **README revamp** — Playwright-captured screenshots of every page type + a gallery section.
6. **Tunnel fixed + durable** — repointed the auto-start `cloudflared` service from a stale token tunnel
   to the local `blog-config.yml` (that was the 503), so it is now a boot service returning 200.
7. **`app.py` refactor** — extracted everything non-route into `src/` packages; `app.py` is now init +
   routes + run only.

---

## 5. Gotchas (read before debugging)
- **MongoEngine:** `Model(**unknown_kwarg)` raises `FieldDoesNotExist` even with `strict=False` — pass only
  declared fields, or insert via the model's raw collection.
- `connect_db()` is idempotent; `src/` is a **regular** package (it has `__init__.py`).
- **`SITE_URL` in the OS env beats `.env`** (`load_dotenv` doesn't override) — clear a stale
  `$env:SITE_URL` if the public URL looks wrong.
- Admin areas need login (`BLOG_ADMIN_USERNAME` / `BLOG_ADMIN_PASSWORD`) — **except `/posts` and `/articles`,
  which are intentionally PUBLIC** (a social-style feed anyone can browse, like LinkedIn/Facebook); only
  drafts are login-gated. Not an auth bug — don't "fix" it.
- **Only one Flask instance per port.**
- `data/` holds the file analytics log + Medium session state (git-ignored).

---

## 6. Open items
- **Commit** the working tree.
- **Medium** import link (the public URL is now permanent).
- **LinkedIn** refresh-token flow (the portal token is short-lived).
- **X / Threads** pending. **YouTube** needs real video.
- **SocialAPI quota** = 10 posts/month; `POST /v1/posts/validate` is free (dry-run button in the UI).

---

## 7. Next session
See `TASKs.md` → "Start here". Top item: the **cloud data-layer abstraction** — one common provider class,
with **media and database each independently swappable** and a shared default provider fallback.
