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
7. **ORM data layer** — MongoEngine Documents in `core/db/` to guarantee field schemas are preserved.
8. **Thin `app.py`** — routes + Flask init + run only; all logic lives in `core/` packages.
9. **Root hygiene** — consolidated structures under `.ai_docs/`, `static/`, and `data/`.
10. **Provider-agnostic storage** — implemented `local`/`cloud` storage layer selector per data type.
11. **LinkedIn refresh-token flow** — long-lived automated refresh token rotations deployed.
12. **YouTube workflow** — video processing page integration and SocialAPI sync blocks.
13. **Analytics + editor** — completed the dashboard metrics overview panels and block composer.
14. **Cloud Migration Engine** — built stdlib SigV4 S3 adapter for Cloudflare R2 (`core/providers/cloud/r2.py`), MongoDB token store persistence, Render deployment blueprint (`render.yaml`), and data/media migration script (`scripts/migrate_to_atlas.py`).
15. **Dual MongoDB URI Support** — added `LOCAL_MONGO_URI` and `ATLAS_MONGO_URI` with auto-selection based on backend environment.
16. **Stealth Admin Lockdown & Hardware Recognition** — hardened `/login`, drafts, and navigation with clean 404s for public readers; implemented 10-year HMAC-SHA256 device recognition tokens (`admin_device_token`) and mTLS header support (`X-Client-Cert-Verified`), eliminating reverse-proxy loopback vulnerabilities.
17. **Medium Violentmonkey POSSE Integration** — deployed userscript (`medium_posse_userscript.user.js` v1.1.0) with automated URL importing (`p/import`) and rich story editor auto-pasting (`new-story`), fully retiring fragile local Playwright cookie dumps.
18. **Documentation & Replication Guide** — complete rewrite of `README.md` with step-by-step setup from scratch, local vs. cloud configuration guides, fixed asset links, Violentmonkey setup steps, and stealth admin documentation.

---

## Next (Session 12 Roadmap: Error Handling, Uptime, SEO & AI Context)

19. **Dynamic Error Architecture & Admin Decoy Route**: Implement styled dark-palette public error page (`templates/error.html`), generic unstyled 404 decoy (`templates/admin_not_found.html`), and edge-aware interception in `@app.before_request` for unauthorized hits to admin paths.
20. **Cold-Start Elimination (`/health`)**: Ultra-lightweight, zero-DB, plain-text 200 OK endpoint for external uptime monitors.
21. **SEO Crawling, Dynamic XML Sitemap & Anti-Indexing**: Dynamic `robots.txt`, XML `sitemap.xml` conforming to schema 0.9, and automatic `X-Robots-Tag: noindex, nofollow, noarchive` injection on private routes and errors via `@app.after_request`.
22. **AI Context & LLM-Friendly Plain-Text Feed (`/llms.txt`)**: Clean Markdown feed of published posts/articles adhering to llmstxt.org specification for AI browsing agents.
23. **LinkedIn engagement & YouTube live run**: Pending SocialAPI personal account beta reply and video upload exercise.