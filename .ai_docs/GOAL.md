# GOAL

## North star

**Write once on the blog (canonical) → on publish it fans out to the social platforms you choose → each
social post carries the blog post's URL → the blog post shows back-links to where it was syndicated.**

Status: the north star is met for six platforms — LinkedIn, Facebook, Instagram, Bluesky, Pinterest, and YouTube — each returning a permalink. Remaining work is reach, robustness, and **portability**.

---

## Principles

- **Blog is canonical.** Every social post links back; the blog records where it went.
- **Bidirectional references.** "Also published on…" is part of the post.
- **Publishing never blocks.** Slow/flaky platform APIs run on a background worker.
- **Idempotent by design.** Re-publishing never double-posts; retry only touches failures.
- **Pluggable adapters.** Each network is one module behind a common interface.
- **Fit the platform, don't mutilate the post.** Rewrite-down rather than cut off.
- **Adapt to the platform's constraints.** Downscale/re-encode/pad media automatically.
- **Free-path testability.** Anything checkable without spending a credit should be.
- **Storage is provider-agnostic.** Nothing is hard-coded to one cloud (see below).

---

## Achieved

1. **Syndication core** — canonical `SITE_URL`, `syndications` per doc, background worker, idempotent re-publish.
2. **LinkedIn** (native API) + **SocialAPI platforms** (Facebook, Instagram, Bluesky, Pinterest).
3. **Media pipeline** — JPEG conversion, downscaling, byte budgeting, aspect scaling adjustments.
4. **Per-platform text** + **LLM rewrite-to-fit** instead of truncation.
5. **Permanent public URL** — Cloudflare **named** tunnel running as a background system boot service.
6. **Free dry-run validation** (`POST /v1/posts/validate`).
7. **ORM data layer** — MongoEngine Documents in `src/db/` to guarantee field schemas are preserved.
8. **Thin `app.py`** — routes + Flask init + run only; all logic lives in `src/` packages.
9. **Root hygiene** — consolidated structures under `.ai_docs/`, `static/`, and `data/`.
10. **Provider-agnostic storage** — implemented `local`/`cloud` storage layer selector per data type.
11. **LinkedIn refresh-token flow** — long-lived automated refresh token rotations deployed.
12. **YouTube workflow** — video processing page integration and SocialAPI sync blocks.
13. **Analytics + editor** — completed the dashboard metrics overview panels and block composer.
14. **Cloud Migration Engine** — built stdlib SigV4 S3 adapter for Cloudflare R2 (`src/providers/cloud/r2.py`), MongoDB token store persistence, Render deployment blueprint (`render.yaml`), and data/media migration script (`scripts/migrate_to_atlas.py`).
15. **Dual MongoDB URI Support** — added `LOCAL_MONGO_URI` and `ATLAS_MONGO_URI` with auto-selection based on backend environment.

---

## Next (Session 10 & 11 Roadmap)

16. **Execute Live Atlas & R2 Data Migration** — Run `scripts/migrate_to_atlas.py` with valid Atlas & R2 credentials to seed cloud storage before production traffic switch.
17. **Link & Deploy on Render** — Connect repository to Render using `render.yaml` to spin up production web service.
18. **LinkedIn engagement** — Staged read path operations pending SocialAPI personal account metric beta validation.