# GOAL

## North star

**Write once on the blog (canonical) → on publish it fans out to the social platforms you choose → each
social post carries the blog post's URL → the blog post shows back-links to where it was syndicated.**

This is POSSE: *Publish Own Site, Syndicate Elsewhere.* The blog is home; social is distribution; links
point both ways.

**Status:** the north star is met for five platforms — LinkedIn, Facebook, Instagram, Bluesky and
Pinterest — each returning a permalink that the page renders as "Also published on…". Remaining work is
reach, robustness and **portability**.

---

## Principles

- **Blog is canonical.** Every social post links back; the blog records where it went.
- **Bidirectional references.** "Also published on…" is part of the post, not an afterthought.
- **Publishing never blocks.** Slow/flaky platform APIs run on a background worker.
- **Idempotent by design.** Re-publishing never double-posts; retry only touches failures.
- **Pluggable adapters.** Each network is one module behind a common interface.
- **Fit the platform, don't mutilate the post.** Rewrite-down rather than cut off.
- **Adapt to the platform's constraints.** Downscale/re-encode/pad media automatically.
- **Free-path testability.** Anything checkable without spending a credit should be.
- **Storage is provider-agnostic.** Nothing is hard-coded to one cloud (see below).

---

## Achieved

1. **Syndication core** — canonical `SITE_URL`, `syndications` per doc, per-post platform selection,
   background worker, back-reference rendering, idempotent re-publish.
2. **LinkedIn** (text **and** images) + **SocialAPI platforms** (Facebook, Instagram, Bluesky, Pinterest).
3. **Media pipeline** — JPEG conversion, downscaling, byte budgeting, Instagram aspect fit, text cards.
4. **Per-platform text** + **LLM rewrite-to-fit** instead of truncation.
5. **Permanent public URL** — Cloudflare **named** tunnel as an auto-start **boot service**.
6. **Free dry-run validation** (`POST /v1/posts/validate`).
7. **ORM data layer** — MongoEngine Documents in `src/db/`; `syndications` is a declared field, so it can
   never be silently dropped.
8. **Thin `app.py`** — routes + Flask init + run only; all logic lives in `src/` packages.
9. **Root hygiene** — notes in `.ai_docs/`, README images in `static/images/readme/`, runtime in `data/`.

---

## Next

10. **Cloud data-layer abstraction** — one **common provider interface**; **media and database each
    independently selectable** across providers, with a **shared default/fallback** provider. (Spec in
    `TASKs.md`; design first.)
11. **Medium** import link; **LinkedIn** refresh-token flow; **X**; **Threads**; **YouTube** video path.
12. Per-platform text overrides; scheduling; metrics read-back.

---

## Later / ideas

- Video path for YouTube; per-platform hand-written overrides; `scheduled_at`; metrics read-back.
- **Multi-user accounts** — today it is a single admin taken from the environment.
- **Moderated comments** — comments are deliberately open and unmoderated for now.
- **Publishing to personal Facebook profiles** — not possible via any permitted API; a Page is the route.

---

## Architecture direction

- **Data access** goes through MongoEngine Documents in `src/db/`.
- **Storage abstraction (next).** A provider layer so the app is not fixed to one cloud: a single
  **common provider class** defines the contract; concrete providers (local filesystem, Azure Blob, S3,
  GCS, MongoDB, …) register into it and are selected by config. **Media and database are chosen
  separately**, and each can fall back to a **shared default** provider.
