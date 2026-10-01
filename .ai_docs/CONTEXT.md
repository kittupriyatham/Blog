# CONTEXT — handoff

_Last updated: 2026-09-23 (**session 3**: live syndication, real tunnel, media pipeline)._
_Companion docs: `GOAL.md` (north star + future goals) and `TASKs.md` (ordered task list)._

---

## 1. North star

Write once on the blog (canonical) → on publish it fans out to the chosen socials → each social
post carries the blog URL → the blog lists where it was syndicated ("Also published on…").
POSSE. See `GOAL.md`.

**Stack:** Flask (`app.py`) + MongoDB + local `media/` (or Azure Blob) · templates in `templates/`,
JS in `static/js/` · runs on Windows locally · deploys via GitHub Actions → Azure Web App.

---

## 2. Where we are right now (end of session 3)

**Five platforms are live and posting for real.**

| Platform | Route | State |
|---|---|---|
| LinkedIn | own adapter (`src/syndication/linkedin.py`) | **posted**, now **with image** |
| Facebook | SocialAPI | **posted** |
| Instagram | SocialAPI | **posted** (after the fixes below) |
| Bluesky | SocialAPI | **posted** |
| Pinterest | SocialAPI | **posted** |
| YouTube | SocialAPI | not offered for text/image posts (needs video) |
| X / Threads / Medium | — | not configured / not done |

**Public URL is permanent:** `https://blog.potluri-krishna-priyatham.tech` — a **named** Cloudflare
tunnel (not a quick tunnel), so syndicated links no longer rot.

**Blog content:** 3 posts, all "Series Post N". Everything else was deleted (backup kept — see §7).

**Nothing is committed.** All work is uncommitted in the working tree.

---

## 3. What happened this session

### Live syndication, end to end
Ran real publishes from the blog and fixed everything they exposed. Final state of "Series Post 2":
all five platforms `posted`, each with a permalink feeding the "Also published on" row.

### Bugs found and fixed (all verified)

1. **Text truncated to the smallest platform's limit.** `run_syndication` composed ONE string shared
   by every platform, so Bluesky's 300-char cap amputated a 401-char post everywhere — the "Note:"
   paragraph vanished on Facebook (6000) and LinkedIn (3000) too. Now composed **per platform**.

2. **Truncation cut far earlier than it needed to.** The boundary finder matched the literal `". "`,
   but posts end sentences with `".\n"` (blank lines between paragraphs), so it missed the real
   boundary and stopped at an earlier sentence. Now matches punctuation followed by whitespace and
   keeps the **latest** usable boundary (137 → 167 chars kept).

3. **Instagram: `content_type` is required when publishing** — and it belongs at the **top level** of
   the request body, not on the target. Nesting it on the target made the API ignore it.

4. **Pinterest: a `board_id` is mandatory on the target** and the account had **zero boards** — no
   default, no fallback. Created a "Blog" board; `SOCIALAPI_BOARD_PINTEREST` pins it.

5. **`413 Request Entity Too Large` on Bluesky + Pinterest.** Not the file being too big (6.37 MB of a
   50 MB allowance) and **not** the storage quota (1.64 MB of 100 MB). It was my own
   `JPEG_REQUIRED = {"instagram","facebook"}` gate: Instagram/Facebook got the converted 576 KB JPEG,
   while Bluesky/Pinterest were handed the raw **6.37 MB PNG**. Now **every** platform gets a prepared
   image (downscaled to ≤1600px and ≤1.5 MB — 6.37 MB → 0.20 MB).

6. **Instagram "aspect ratio is not supported"** — 3006×1376 is ratio 2.185, Instagram allows
   **0.8–1.91**. Now padded (not cropped, so nothing is lost) into range for Instagram only.

7. **LinkedIn posted no media** — the adapter explicitly ignored `media`. Now does
   `initializeUpload` → `PUT` → attaches the image URN.

8. **Error messages hid the cause.** `_error_message` only read `error.message`, so
   "fix the listed issues" arrived with no list. Now includes `code`/`details`/`issues`/`meta` —
   that's what revealed fix #3.

### Faster/cleaner posting
- **LLM rewrite-to-fit** (`src/syndication/rewrite.py`): an over-long post is **rewritten** to fit the
  platform's limit (link included) instead of being cut off. Falls back to trimming when no model is
  available, so publishing never depends on it. Cached per (text, limit).
- **Retry buttons** for failed platforms, with live status polling. Never re-posts something already
  `posted`.
- **Free dry-run validation** — see §5. Built because the monthly quota ran out.

### UI
- Social icon rows on the **feed**, **/posts** and the post page (one shared partial, compact variant).
  Greyed = not syndicated; YouTube now shows too instead of vanishing.
- **"see more" expands in place** instead of navigating to the post page.
- Live **character counter** in the editor, reserving the link length.

### Infrastructure
- **Named Cloudflare tunnel** `blog` → `blog.potluri-krishna-priyatham.tech` (own config file, apex
  portfolio untouched, existing Ollama tunnels preserved).
- **`SITE_URL` was being silently ignored** — see §6, this cost real debugging time.

---

## 4. Key files

| Path | What |
|---|---|
| `app.py` | routes, syndication core/worker, retry + validate endpoints, `rich_text`, comments, tags |
| `src/syndication/__init__.py` | public surface, per-platform composition, `media_for`, truncation |
| `src/syndication/base.py` | `Syndicator` interface, registry, `SyndicationError` |
| `src/syndication/socialapi.py` | Facebook/Instagram/Bluesky/Pinterest/YouTube via SocialAPI — targets, `platform_data`, media prep, boards, `validate()` |
| `src/syndication/linkedin.py` | LinkedIn adapter — publish (with image), delete, check, version self-heal |
| `src/syndication/imageprep.py` | flatten alpha → JPEG, downscale, byte budget, aspect fit |
| `src/syndication/rewrite.py` | LLM rewrite-to-fit (Gemini), cached, safe fallback |
| `src/syndication/textcard.py` | renders a text-only post as a JPEG card (IG/Pinterest) |
| `templates/_social_icons.html` | shared icon row (full + compact) |
| `templates/_syndication_options.html` | platform checkboxes, live char counter, guard |

**Endpoints added:** `/api/syndication/retry`, `/api/syndication/status/<id>`, `/api/syndication/validate`.

---

## 5. Free dry-run validation (important given the quota)

SocialAPI has `POST /v1/posts/validate` — same checks as publishing, nothing sent, **no credit spent**
(credits are charged only on publish/schedule). Wired into the app as a
**"Validate (free)"** button on the post page.

It validates with media prepared exactly as a real publish would, so it catches size/aspect problems
before you spend a post. First run already flagged: *"images are not supported on youtube"*.

**Current quota:** 10 posts/month on the free hobby tier — **exhausted for this month.** Use validate
until it resets.

---

## 6. Environment gotchas (these each cost real time — read before debugging)

- **`SITE_URL` in the OS environment beats `.env`.** `load_dotenv()` does **not** override an existing
  env var, so a stale `SITE_URL` in the shell silently won every time and every `.env` edit did
  nothing. Fix: `Remove-Item Env:SITE_URL` (or open a fresh terminal) before starting Flask.
  **Check `$env:SITE_URL` first whenever the public URL looks wrong.**
- **Cloudflare quick tunnels rotate and die.** The process can be alive while its hostname no longer
  resolves — check the URL, not the process. Fixed permanently by the named tunnel.
- **Cloudflare returns `403 / error 1010`** to `Python-urllib`. Always send a real `User-Agent`.
- **Gemini 2.5 Flash spends output tokens on thinking** — with a small `maxOutputTokens` the visible
  reply came back clipped mid-word. `thinkingConfig.thinkingBudget = 0` for rewrite-to-fit.
- **Pillow: keep image work inside `with Image.open(...)`.** `_flatten` returns the opened object
  unchanged when the file is already RGB, and it's unusable once the context closes
  (`AssertionError: self.fp is not None`) — this broke every RGB attachment.
- **Aspect padding then resizing can round back out of range** (padded to 1.910 → resized to 1.912).
  Ceiling the pad and re-checking the saved file is what makes it stick.
- **`flask run --debug` reloads `.py` (and templates), but NOT `.env`.** Restart for env changes.
- **Only one Flask instance per port.** Werkzeug's `SO_REUSEADDR` on Windows lets several bind the same
  port and requests route unpredictably.
- **The `posts` collection holds both posts and articles**; content lives in `blocks`, not a top-level
  `content` field.

---

## 7. Open items / next session

**Blocked / waiting**
- **SocialAPI quota exhausted** (10/month) — publish again after it resets; validate freely until then.
- **Facebook as a personal profile is not possible.** SocialAPI's Facebook connector is **Page-only**
  (all its permissions are Page-scoped) and Meta doesn't let third-party apps publish to personal
  timelines. Options: keep posting to the Page, or manual posting. (Browser automation would break
  Meta's ToS — needs an explicit decision.)
- **LinkedIn token** is from the portal generator with a short TTL → refresh-token flow still pending.
- **Medium** needs a public URL — now permanently available, so the import link should work.

**Known imperfections**
- Links already syndicated while the quick tunnel was live point at a **dead hostname** and can't be
  repaired retroactively. Everything from now on is permanent.
- The named tunnel runs as a **plain process**, so it won't survive a reboot — auto-start not set up.
- YouTube is offered but a text/image post can never satisfy it (needs video).

**Housekeeping**
- Deleted posts are backed up at
  `%TEMP%\commandcode\...\scratchpad\posts-backup-20260923-223432.json` (all 9 docs) — move it
  somewhere durable if it should outlive the session.
- `media/` holds the original 6.37 MB PNG plus its prepared `.jpg`/`_ig.jpg` derivatives.
- **Nothing is committed to git yet.**
