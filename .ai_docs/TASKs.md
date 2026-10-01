# TASKs

Ordered ledger. Companions: `GOAL.md` (why), `CONTEXT.md` (where we are).
**Sessions 6–8 are committed and pushed.**

---

## Start here (next)

| # | Task | Why / done looks like |
|---|------|------------------------|
| 1 | **YouTube video path** | Attach `static/video/video_<post_id>` via `media_for()`; emit a `youtube` metadata block from `_platform_data()` (title/description/tags from the doc; category/privacy from env; madeForKids=false). Confirm the field names against SocialAPI's YouTube API. |
| 2 | **Permanent domain** | Point `kittupriyatham.com` → `blog.kittupriyatham.com` (the current domain is good for ≥1 year). |
| 3 | **Clear a stale `SITE_URL` env var** if the public URL reverts | `Remove-Item Env:SITE_URL`, or `load_dotenv(override=True)`. |

### Task 1 — YouTube (design)
The SocialAPI adapter sends only `text`/`targets`/`media`; `_platform_data()` is `None` outside Instagram, so
YouTube gets no metadata. Add: (a) `media_for(doc)` attaches `static/video/video_<post_id>.<ext>`
(`_media_kind` already classifies it as `video`; `REQUIRES_VIDEO={"youtube"}` already gates it);
(b) `_platform_data(media, doc)` emits `{"youtube": {title, description, tags, category, privacy,
madeForKids:false}}` — title from `doc.title`/first line (≤100), description = text + canonical URL, tags =
`doc.tags`, category/privacy from env (`YOUTUBE_CATEGORY`/`YOUTUBE_PRIVACY`); `publish_detailed` already
receives `doc` (currently ignored). Optional: per-post overrides. Confirm the exact SocialAPI field names.

---

## Done (session 8)

- **LinkedIn refresh-token flow** — `src/syndication/linkedin_token.py` (an on-disk token store
  `data/linkedin_token.json` + OAuth refresh; stdlib only; **backward compatible**: no creds → static
  `LINKEDIN_ACCESS_TOKEN` as before) wired into `linkedin.py` (all 4 token reads). `.env.example` documents
  `LINKEDIN_CLIENT_ID`/`LINKEDIN_CLIENT_SECRET`/`LINKEDIN_REDIRECT_URI` + the setup CLI.
- **Free dry-run Validate** on `welcome_post` → facebook/instagram/youtube/bluesky/pinterest all `valid`
  (bluesky warns 282/300); linkedin has no dry-run (native adapter). No credit spent.
- **Medium import** verified as-is (copies the canonical URL + opens `medium.com/p/import`).
- **Rigorous full-project test pass** (51/53) — fixed stale Azure references, the cloud provider
  `exists()/delete()` error contract, and an orphaned draft's status; confirmed the public `/posts` +
  `/articles` behaviour is intentional.

## Done (session 7)

- **Cloud data-layer abstraction** — a `local`/`cloud` selector per data type (media, database) with
  pluggable adapters (config-driven HTTP upload; `register_adapter`; **no cloud SDK**), wired behind
  `media.*` / `db.*` (no call-site change). Azure removed.

## Done (session 6) — committed + pushed

- Fixed the **"Also published on"** row; **enforced the MongoEngine ORM**; removed the file store; **root
  cleanup** (`.ai_docs/`, `static/images/readme/`, `data/`); **README revamp**; tunnel as an auto-start
  **boot service**; **`app.py` refactored** to routes + init + run.

---

## Later / polish

| Task | Notes |
|------|-------|
| Per-platform text overrides | Rewrite-to-fit is automatic; allow hand-written short versions. |
| Scheduling | SocialAPI accepts `scheduled_at`; the blog publishes immediately. |
| Metrics read-back | Likes/comments per platform on the post page. |
| Expand the Attach menu | Partial — link-preview cards, quote/callout/table/poll. |
| `media/` tidy-up | Still keeps the original large PNG beside its prepared derivatives. |

## Known issues (not yet tasks)

- **SocialAPI free tier = 10 posts/month** (validate is free).
- **Facebook is Page-only** — no personal-profile publishing via any permitted API.
