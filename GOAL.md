# GOAL

## North star

**Write once on the blog (canonical) → on publish it fans out to the social platforms you choose → each
social post carries the blog post's URL → the blog post shows back-links to where it was syndicated.**

This is POSSE: *Publish Own Site, Syndicate Elsewhere.* The blog is home; social is distribution; links
point both ways.

**Status: the north star is now met for five platforms** — LinkedIn, Facebook, Instagram, Bluesky and
Pinterest all publish from the blog, each returning a permalink that the post page renders as
"Also published on". The remaining work is reach, robustness and polish, not the core loop.

## Vision

A personal content hub — posts, long-form articles, photos, videos and songs — that behaves like a
publishing platform, not a website with a "share" button. You write in one place, and it appears
everywhere it should, with the canonical link intact and a way to see where each piece landed.

---

## Principles

- **Blog is canonical.** Every social post links back to the blog, and the blog records where it went.
- **Bidirectional references.** "Also published on…" is part of the post, not an afterthought.
- **Publishing never blocks.** Slow/flaky platform APIs run on a background worker; the UI stays usable.
- **Idempotent by design.** Re-publishing never double-posts — already-sent platforms are skipped, and
  retry only ever touches failures.
- **Pluggable adapters.** Each network is one module behind a common interface; swapping providers is a
  one-file change.
- **Fit the platform, don't mutilate the post.** Where a platform is smaller than the post, rewrite it
  down rather than cutting it off mid-thought.
- **Adapt to the platform's constraints, not the author's patience.** Downscale, re-encode and pad
  media automatically; the author should never have to prepare a file per network.
- **Free-path testability.** Anything that can be checked without spending a credit should be.

---

## Milestones

### Achieved

1. **Syndication core** — canonical `SITE_URL`, `syndications` on each doc, per-post platform selection,
   background worker, back-reference rendering, idempotent re-publish.
2. **LinkedIn** — own adapter, publishing text **and images**, with delete and read-only token check.
3. **SocialAPI platforms** — Facebook, Instagram, Bluesky, Pinterest live; YouTube available.
4. **Media pipeline** — automatic JPEG conversion, downscaling and byte budgeting for every upload;
   aspect-ratio fitting for Instagram; text cards for text-only posts.
5. **Per-platform text** — each platform composed at its own limit, with LLM rewrite-to-fit instead of
   truncation.
6. **Permanent public URL** — named Cloudflare tunnel on `blog.potluri-krishna-priyatham.tech`, so
   syndicated links don't rot.
7. **Free dry-run validation** — validate any post against every platform's rules without spending a
   post credit.

### Next

8. **Medium** — one-click import link (the public URL now makes this viable), optionally a Playwright
   worker later.
9. **LinkedIn refresh-token flow** — replace the short-lived portal token so it stops expiring.
10. **X** — a config change plus a platform id via SocialAPI, not a new integration.
11. **Threads** — its connector has been broken (`platform.threads.auth`); revisit now the other
    Meta platforms work.
12. **Tunnel durability** — auto-start the named tunnel so a reboot doesn't take the blog offline.

### Later / ideas

13. **Video path for YouTube** — the one platform the current pipeline can never satisfy, since it
    needs real video rather than an image.
14. **Per-platform text overrides** — let the author hand-write the short version instead of always
    accepting the generated one.
15. **Scheduling** — SocialAPI supports `scheduled_at`; the blog currently always publishes immediately.
16. **Metrics read-back** — likes/comments per platform could flow back onto the post page.

## Non-goals (for now)

- Multi-user accounts (single admin from env).
- Moderated comments (the comment system is deliberately open and unmoderated).
- Publishing to **personal** Facebook profiles — not possible via any permitted API; a Page is the
  supported route and the connector is Page-only by design.
