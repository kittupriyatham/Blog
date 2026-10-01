# TASKs

Ordered task ledger. Companion to `GOAL.md` (why) and `CONTEXT.md` (where we are).

Two groups:
- **Goal tasks** — serve the north star in `GOAL.md`.
- **Other tasks** — useful, not required for the goal.

**Nothing here is committed to git yet** — that is deliberately task 1.

---

## Start here (tomorrow)

| # | Task | Why / done looks like |
|---|------|------------------------|
| 1 | **Commit the working tree** | A whole session of uncommitted work (imageprep, rewrite, validate, retry, icons, tunnel config). Commit before anything else so it can't be lost. |
| 2 | **Move the post backup somewhere durable** | `posts-backup-20260923-223432.json` (all 9 docs) currently lives in the session scratchpad, which is cleaned up. Copy into the repo or `~/backups`. |
| 3 | **Tunnel is durable; Flask stopped (per instruction)** | Tunnel now auto-starts at every logon via a Windows **Startup-folder** launcher (`start-blog-tunnel.bat`, runs `cloudflared tunnel --config %USERPROFILE%\.cloudflared\blog-config.yml run blog` using the long-lived credentials file — no short-lived run token, no admin needed). A detached instance is live now; `cloudflared tunnel list` shows the `blog` tunnel with active connections and the public URL returns 502 (tunnel IS routing — 502 only because Flask is stopped, as requested). Restart Flask with `set SITE_URL=https://blog.potluri-krishna-priyatham.tech && venv\Scripts\flask run --debug --port 5000`. |
| 4 | **Stale `cloudflared` Windows service** | A pre-existing `cloudflared` service (AUTO_START, runs as LocalSystem) exists at `C:\Program Files (x86)\cloudflared\cloudflared.exe tunnel run --token-file C:\ProgramData\cloudflared\token`, but its token is **stale** (blog tunnel showed no connection). I'm **not elevated**, so I can't refresh `C:\ProgramData\cloudflared\token` or stop/restart the service. To make the service the single durable bearer, run **one** elevated command: `net stop cloudflared; $t=(cloudflared tunnel token bbfdeca1-f2ab-4563-a9ae-dc005a22e46f); [IO.File]::WriteAllText('C:\ProgramData\cloudflared\token',$t); net start cloudflared` — then delete the Startup launcher (it becomes a fallback). |
| 5 | **Clear the stale `SITE_URL` env var** | `Remove-Item Env:SITE_URL` before starting Flask, or switch `load_dotenv()` to `override=True`, or else a leftover value reverts the public URL. |

---

## Goal tasks

### 1. Republish the failed Series Post 3  *(when the quota resets)*
The fixes for its three failures (413 on Bluesky/Pinterest, Instagram aspect ratio, LinkedIn media) are
in and **verified by dry-run validation** — they have not yet been proven by a real publish.

Use **Validate (free)** first, then hit **Retry** on each failed platform. Expect:
- Instagram → padded `_ig.jpg`, ratio 1.909
- Bluesky / Pinterest → the 0.20 MB prepared JPEG
- LinkedIn → image attached via `initializeUpload`

### 2. Medium import link
Medium has no write API. The one-click path is its **import** (`medium.com/p/import`) with the canonical
URL pre-filled, which also sets the canonical link back to the blog. Previously blocked on needing a
public URL — the named tunnel now provides a permanent one, so this should work.

A button already exists on the post page; verify it opens with the URL and completes an import. The
later, hands-off option is a **separate** Playwright worker — never inside the blog process.

### 3. LinkedIn refresh-token flow
The current token came from the portal's generator, has a short TTL, and has already expired once
(causing a bogus 401 mid-session). Build the authorization-code flow with a refresh token and refresh
before expiry. Scopes: `openid profile w_member_social`.

### 4. Tunnel durability  ✅ resolved (no-admin)
The named `blog` tunnel now starts automatically at every logon via a Windows **Startup-folder**
launcher (`start-blog-tunnel.bat`: `cloudflared tunnel --config %USERPROFILE%\.cloudflared\blog-config.yml run blog`)
using the long-lived credentials file — no short-lived run token, no admin required. A detached instance
is live now; `cloudflared tunnel list` shows the `blog` tunnel connected, and the public URL returns 502
(tunnel routing correctly — 502 only because Flask is stopped). A pre-existing `cloudflared` Windows
service (AUTO_START) has a stale token and can't be refreshed without elevation — see task #4 in
"Start here".

### 5. X (Twitter)
Now a config change plus a platform id rather than a new integration — SocialAPI supports X (and
bring-your-own-key). X has no free tier (~$0.20 per link post), so decide whether it's worth it.

### 6. Threads — revisit
The connector was broken earlier (`platform.threads.auth`). Worth retrying now that Facebook and
Instagram work through the same provider.

### 7. Video path for YouTube
YouTube is the one platform the pipeline can never satisfy: it needs real video, and a text card is an
image. Either accept that YouTube is manual, or build a real video-generation step.

---

## Other tasks

| Task | Status | Notes |
|------|--------|-------|
| Expand the Attach menu (link preview card, quote/callout/table/poll) | partial | Fetched link-preview cards still render as plain autolinks; the article editor's insert menu wasn't extended with the newer blocks. |
| Per-platform text overrides | not started | The rewrite-to-fit is automatic; the author may want to write the short version by hand. |
| Scheduling | not started | SocialAPI accepts `scheduled_at`; the blog always publishes immediately. |
| Metrics read-back | not started | Likes/comments per platform on the post page. |

---

## Known issues (not yet tasks)

- **Links syndicated during the quick-tunnel era are dead.** They point at rotated `trycloudflare.com`
  hostnames and cannot be repaired retroactively. Everything from the named tunnel onward is permanent.
- **Facebook posts to a Page, not a personal profile.** Not fixable via any permitted API — SocialAPI's
  connector is Page-only and Meta forbids personal-timeline publishing by third-party apps.
- **SocialAPI free tier = 10 posts/month.** Exhausted for this month. `POST /v1/posts/validate` is free
  and wired into the UI, so testing can continue meanwhile.
- **`media/` keeps the original 6.37 MB PNG** alongside its prepared derivatives now that uploads are
  downscaled.
