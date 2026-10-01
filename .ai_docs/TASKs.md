# TASKs

Ordered ledger. Companions: `GOAL.md` (why), `CONTEXT.md` (where we are).
**Nothing is committed to git yet** — that is an early task.

---

## Start here (tomorrow)

| # | Task | Why / done looks like |
|---|------|------------------------|
| 1 | **Cloud data-layer abstraction** (design first, then implement) | Make storage provider-agnostic — see the spec below. |
| 2 | **Commit the working tree** | A whole session uncommitted: ORM wiring, syndication-bar fix, removals, root cleanup, README revamp, tunnel service, `app.py` refactor. |
| 3 | **Medium import link** | Public URL is permanently available; verify the button opens `medium.com/p/import` pre-filled and completes. |
| 4 | **LinkedIn refresh-token flow** | Replace the short-lived portal token. Scopes `openid profile w_member_social`. |
| 5 | **Clear a stale `SITE_URL` env var** if the public URL reverts | `Remove-Item Env:SITE_URL`, or `load_dotenv(override=True)`. |

### Task 1 — Cloud data-layer abstraction (spec to design tomorrow)

**Goal:** the app must not be fixed to one storage backend. Introduce a provider layer so **media** and
**database** can each live on *any* cloud — local filesystem / local `mongod` today; Azure Blob / S3 / GCS
/ Mongo Atlas / others later.

**Requirements**
- **One common provider class/interface** that every concrete provider implements, plus a registry
  (register + select by name).
- **Per data-type selection:** `media` and `database` are configured **independently** — media on provider
  A and the database on provider B must both be valid at once.
- **Common vs specific provider:** for each data type you can set a **specific** provider *and/or* fall
  back to a **shared default** provider — resolved per situation.
- **Config-driven (env):** a default provider + per-type overrides, resolved at startup.
- **Contract per type** — media: put / get / delete / exists / public URL; database: connect / health +
  the document access the ORM needs.
- **Swappable:** adding a provider = one new class + a registration, no call-site changes.

**Do not implement yet — design the interface + registration + selection first.**

---

## Done this session (6)

- Fixed the **"Also published on"** row — it now **always** renders (previously hidden when nothing was
  posted, e.g. failed-only posts).
- **Enforced the MongoEngine ORM**; dropped the file store (`blog.json`, `sync_storage`, `src/storage`,
  `dbinit`).
- **Root cleanup:** notes → `.ai_docs/`, README images → `static/images/readme/`, runtime → `data/`.
- **README revamp** with Playwright screenshots of every page type.
- **Tunnel** repointed to the local config as an auto-start **boot service**.
- **`app.py` refactored** to routes + init + run only; logic moved into `src/` packages.

---

## Goal tasks (remaining)

- **Republish the failed Series Post 3** when the SocialAPI quota resets — *Validate (free)* first, then
  **Retry** on each failed platform (Instagram padded JPEG; Bluesky/Pinterest prepared JPEG; LinkedIn image).
- **Medium** one-click import link.
- **LinkedIn** refresh-token flow.
- **X / Threads** — config + platform id, not new integrations.
- **YouTube** — needs a real video path (a text card is an image).

## Other / later

| Task | Status | Notes |
|------|--------|-------|
| Per-platform text overrides | not started | Rewrite-to-fit is automatic; allow hand-written short versions. |
| Scheduling | not started | SocialAPI accepts `scheduled_at`; the blog publishes immediately. |
| Metrics read-back | not started | Likes/comments per platform on the post page. |
| Expand the Attach menu | partial | Link-preview cards, quote/callout/table/poll. |
| Permanent domain | planned | The current `blog.potluri-krishna-priyatham.tech` is good for **≥1 year**; add `kittupriyatham.com` and serve the blog at `blog.kittupriyatham.com` (permanent). |
| Web analytics | done | First-party beacon; file (`data/analytics.jsonl`) or Mongo store; `/admin/analytics`. |

## Known issues (not yet tasks)

- **SocialAPI free tier = 10 posts/month** (exhausted this month); `POST /v1/posts/validate` is free.
- **Facebook is Page-only** — no personal-profile publishing via any permitted API.
- **`media/` keeps the original large PNG** alongside its prepared derivatives.
