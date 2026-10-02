# TASKs

Ordered ledger. Companions: `GOAL.md` (why), `CONTEXT.md` (where we are).
**Sessions 6–8 are committed and pushed. Session 9's work is UNCOMMITTED** (the user pushes it).

---

## Start here (next)

| # | Task | Why / done looks like |
|---|------|------------------------|
| 1 | **LinkedIn engagement via SocialAPI — blocked on their reply** | LinkedIn posting is settled: it publishes **natively** as the personal profile (official API, so no SocialAPI post credit is spent). Its *metrics* need SocialAPI's `linkedin_page` beta + `connection_type: "personal"` (that variant grants `r_member_postAnalytics` / `r_member_profileAnalytics`, which LinkedIn denies our own app). Emailed `support@social-api.ai`; reply expected **Mon** (approval not required to act on it). **On reply:** set `SOCIALAPI_METRIC_PLATFORMS = {"linkedin"}` in `socialapi_metrics.py` (one line, already staged) and verify the live read. **Open question:** can SocialAPI read a member post by URN (`urn:li:share:<id>`) that it did not publish? |
| 2 | **Threads / X for long-form** | X stays short-post-only until `TWITTER_SUBSCRIPTION=1`; Threads is not pursued at all. |

**Dropped:** permanent domain — the user will update `SITE_URL` manually when the domain is ready.
**Deferred (do later):** scheduling (`scheduled_at`), multi-user accounts, moderated comments.

---

## Done (session 9)

- **LinkedIn posts as the personal profile** — `LINKEDIN_ORGANIZATION_URN` blanked; `author_urn()` resolves to
  the member URN; the token store was re-minted with `w_member_social` **and** the org scopes (one consent
  covers both targets, so switching later needs no new re-auth). Verified: post author, `is_configured`, 30 routes.
- **LinkedIn *member* metrics are API-gated (proven live)** — `memberCreatorPostAnalytics` and `socialActions`
  both return `403 partnerApi…`; they need `r_member_postAnalytics` = the Community Management API, which must
  be an app's *only* product. `linkedin_metrics.py`'s no-org branch is now a neutral hint, not a "set the org URN" nag.
- **SocialAPI LinkedIn metrics path staged (inactive)** — `socialapi_metrics.SOCIALAPI_METRIC_PLATFORMS`
  (empty today) routes a *natively-published* platform's metrics to SocialAPI; `socialapi.py` records that
  LinkedIn is deliberately not a SocialAPI publishing platform (no post credit, no id collision).
  Rationale: **post through the official API, read metrics from SocialAPI** (SocialAPI posting costs credits).
- **YouTube video path built** — a dedicated `/youtube/<post_id>` page (+ an inline composer panel) collects the
  full upload metadata into `doc["youtube"]`; the SocialAPI adapter sends it as the `platform_data.youtube`
  block; a video-only post is valid. *(Not yet exercised end-to-end with a real upload — that spends a credit.)*
- **Per-platform text — rigorously tested, no bugs** — 100+ checks: per-platform limits, link suffix,
  exact-fit vs over-limit boundaries, per-platform independence, empty body, article-vs-post, CRLF, non-public
  URL, `_preview_shortened` mirroring `compose_text`, and `/api/syndication/preview` (auth, shape,
  preview↔publish consistency, Medium correctly dropped for posts). What exists is the **auto per-platform
  compose + preview**; a *hand-written* per-platform override is still the "Later" item.
- **Stale `SITE_URL` fixed in code** — `src/config/settings.py` now prefers the `.env` value for `SITE_URL` and
  writes it back into `os.environ`, so a stale OS-level variable can no longer shadow the configured public URL
  (it used to win, because `load_dotenv()` never overrides a real env var). Verified with a simulated stale var.
- **Analytics + editor (built earlier this session)** — per-post × per-platform social metrics + first-party
  blog analytics; the editor gained per-platform preview, 14 rich blocks, attachment remove/reorder.

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
