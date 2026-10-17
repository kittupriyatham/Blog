# Blog

A small, opinionated Flask blog with MongoDB storage (via MongoEngine), multi-platform POSSE syndication (Medium / LinkedIn / X / Bluesky / Instagram / Pinterest / Facebook / YouTube), first-party cross-channel analytics, and a Cloudflare tunnel for a public URL.

---

## Screenshots

### Public site

| Feed | Post |
| --- | --- |
| ![Feed — every card shows the "Also on:" syndication row](static/images/readme/home.png) | ![Post — "Also published on:" row plus comments](static/images/readme/post-detail.png) |

| Article | Sign in |
| --- | --- |
| ![Article](static/images/readme/article-detail.png) | ![Sign in](static/images/readme/login.png) |

### Admin

| Post Manager | Articles |
| --- | --- |
| ![Post Manager](static/images/readme/dashboard-posts.png) | ![Articles](static/images/readme/dashboard-articles.png) |

| New post | New article |
| --- | --- |
| ![New post](static/images/readme/editor-post.png) | ![New article](static/images/readme/editor-article.png) |

| Edit post | Edit article |
| --- | --- |
| ![Edit post](static/images/readme/edit-post.png) | ![Edit article](static/images/readme/edit-article.png) |

| Analytics |
| --- |
| ![Analytics dashboard](static/images/readme/dashboard-analytics.png) |

---

## Repo visualization

![Visualization of the codebase](static/images/readme/repo-diagram.svg)

---

## Requirements

- Python 3.9+
- MongoDB — MongoEngine requires an active database instance (the in-process `mongomock` fallback is **not** supported). Works with any MongoDB-compatible deployment URI (local or cloud-hosted via MongoDB Atlas).
- Cloudflared (optional — only needed for a public domain instead of `localhost`)

## Local setup

```bash
git clone <repo>
cd Blog
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows (cmd):
.venv\Scripts\activate
pip install -r requirements.txt

# 1) Create your env from the example and fill in the secrets:
cp .env.example .env

# 2) Collections + indexes are created automatically on first boot
#    (ensure_schema() in core/db/__init__.py) - no init script and no file seed required.

# 3) Run the site:
python app.py          # -> http://localhost:5000
```

### Public URL via Cloudflare tunnel

The tunnel is defined by `~/.cloudflared/blog-config.yml` — a named `blog` tunnel routing your domain to `http://127.0.0.1:5000`. It runs as an auto-starting system boot service:

```bash
cloudflared --config "%USERPROFILE%\.cloudflared\blog-config.yml" tunnel run blog
```

Set `SITE_URL=https://<your-domain>` in `.env` so canonical links and syndication engines map to the public address. Priority routing ensures that `.env` specifications explicitly override loose system or ambient environment configurations.

---

## Architecture & Layout

```text
app.py                       # Flask init + routes + app.run (thin controller layer)
core/
  __init__.py                # regular package marker
  config/    settings.py     # env variables + R2/Atlas infrastructure configurations
  providers/ base.py registry.py local.py cloud/{media,mongo,http,r2}.py # local vs cloud storage targets
  media/     uploads.py paths.py
  content/   rich_text.py helpers.py urls.py
  analytics/ events.py reports.py
  notify/    telegram.py
  syndication/ base.py socialapi.py socialapi_metrics.py linkedin.py linkedin_token.py linkedin_metrics.py imageprep.py rewrite.py textcard.py runner.py
  db/        models.py + __init__.py (connect_db, ensure_schema) + migrate_to_atlas.py
templates/  static/  media/  data/  .ai_docs/
```

- **Thin Controller:** `app.py` is restricted solely to application initialization and routing; core operational logic resides cleanly within decoupled `core/` modular packages.
- **Data Access:** Enforced strictly via MongoEngine Document mapping classes (`Post`/`Comment`/`AnalyticsEvent`) to guarantee structural schema arrays are preserved and never silently dropped. Flat-file storage pipelines are fully deprecated.
- **Gotchas:** Gated administrative tools require session logins. However, feed views (`/posts`, `/articles`) are left intentionally public as open visual feeds.

---

## Storage & Cloud Migration Framework

The application implements a decoupled provider-agnostic storage abstraction layer allowing independent `local`/`cloud` target splits for database layers and asset storage blocks via configuration flags.

1. **Database Layer:** Supports local `mongod` configurations or remote MongoDB Atlas connection clusters. The LinkedIn OAuth token engine stores authentication metrics directly inside a persistent Mongo collection to guarantee deployment survival across ephemeral container instances.
2. **Media & Assets Backend:** Leverages a lightweight, standalone `stdlib`-only SigV4 Cloudflare R2 upload adapter (`core/providers/cloud/r2.py`) eliminating external cloud provider runtime SDK dependencies. Extended parameters are fully documented within `.env.example`.
3. **Migration Tools:** A complete data utility script (`core/db/migrate_to_atlas.py`) manages the direct porting of legacy posts, comment metrics, token assets, and media components out of local file paths onto cloud infrastructure setups.

---

## Syndication & Content Optimization

The blog operates under strict **POSSE** rules (*Publish Own Site, Syndicate Elsewhere*). 

- **Automated Text Engine:** A multi-channel formatting pipeline evaluates text strings against specific destination boundaries (e.g. character thresholds, carriage returns, media links, and preview shorteners), triggering dynamic LLM contextual rewrites to fit platform profiles safely without harsh truncation metrics.
- **LinkedIn Integration:** Dispatches content directly to **personal member profiles** using the official native API framework (bypassing commercial post credit requirements). Volatile tokens rotate seamlessly via automated long-lived background refresh flows. 
- **YouTube Pipeline:** Incorporates dedicated tracking pages and inline panels to capture video metrics and metadata bundles, converting files smoothly inside the SocialAPI adapter workflows.
- **Validation Engine:** Employs dry-run post validations (`POST /v1/posts/validate`) across Facebook, Instagram, YouTube, Bluesky, and Pinterest channels for credit-free integrity checks prior to deployment publishing.

### Manual Setup for Optional Integrations

> [!NOTE]
> **Are these required for a new setup?**
> **No.** The blog runs completely out of the box without LinkedIn or Medium. All core features (publishing posts & articles, comments, theme toggles, media uploads, and first-party analytics) work immediately. Configure these only if you want automatic syndication to these specific platforms.

#### 1. Official LinkedIn Integration (OAuth 2.0 Self-Refreshing Token)
LinkedIn's official API issues 60-day access tokens. The blog automatically refreshes this token in the background and saves it to MongoDB (`secrets` collection) so it never expires.

1. Create an app in the [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps).
2. Add your credentials to `.env`:
   ```env
   LINKEDIN_CLIENT_ID=your_client_id
   LINKEDIN_CLIENT_SECRET=your_client_secret
   LINKEDIN_REDIRECT_URI=https://www.linkedin.com/developers/tools/oauth/redirect
   ```
3. Generate the authorization URL:
   ```bash
   python -m core.syndication.linkedin_token
   ```
4. Open the printed URL in your browser, approve access, and copy the `code` parameter from the redirect URL address bar.
5. Exchange the code and store the token:
   ```bash
   python -m core.syndication.linkedin_token <copied_code>
   ```

#### 2. Dev.to & Hashnode (Direct Official APIs — No Browser Extension Needed)
Both Dev.to and Hashnode support 100% headless background publishing directly from the blog without any browser tools:

* **Dev.to**:
  1. Go to **Dev.to $\rightarrow$ Settings $\rightarrow$ Extensions $\rightarrow$ DEV Community API Keys**.
  2. Generate a key and add it to `.env`:
     ```env
     DEVTO_API_KEY=your_devto_api_key
     ```
* **Hashnode**:
  1. Go to **Hashnode $\rightarrow$ Account Settings $\rightarrow$ Developer $\rightarrow$ Personal Access Token**.
  2. Copy your token and your Blog Publication ID (found under your publication settings), then add them to `.env`:
     ```env
     HASHNODE_ACCESS_TOKEN=your_token
     HASHNODE_PUBLICATION_ID=your_publication_id
     ```

#### 3. Medium POSSE Integration
Medium permanently shut down their public write API. However, Medium's official server-side URL importer at `https://medium.com/p/import` works directly with your public blog:

* **Direct Medium Importer (Default & Simplest):**
  1. On any published article page (`/article/<id>`), click the **"Medium Importer"** button (or "Publish to Medium").
  2. The button copies your canonical blog article URL directly to your clipboard and opens `https://medium.com/p/import`.
  3. Paste the URL and click **Import Story**. Medium imports the title, formatting, cover image, and body directly from your blog while automatically attributing canonical SEO credit to your site.
  4. *No Playwright, LinkedIn, Dev.to, or third-party intermediaries required.*

* **Alternative: Browser Userscript Bridge (Direct in Tampermonkey / Violentmonkey):**
  If you prefer a 1-click auto-fill directly into Medium's story editor (`medium.com/new-story`), install the userscript located at:
  [`static/js/medium_posse_userscript.user.js`](file:///static/js/medium_posse_userscript.user.js)
  Clicking **"Syndicate to Medium"** opens Medium's editor in your browser and automatically injects the story title and formatted content into the editor.

---

## Analytics & Editor Controls

- **Cross-Channel Monitoring:** The unified analytics dashboard (`/admin/analytics`) aligns first-party web metrics against granular per-post and per-platform social interactions (integrating native LinkedIn and SocialAPI metric paths seamlessly).
- **Persistence:** Client actions are routed server-side via `navigator.sendBeacon` to protect tracking data events across rapid reader browsing.
- **Geo-Tracking:** Optional IP-hash analytics (`ANALYTICS_GEO=1`) verify city/region locations via salted beacons without capturing or persisting raw visitor IPs.
- **Rich Editor:** The writing interface features 14 customizable text blocks, live side-by-side platform rendering cards, and fluid drag-and-drop media attachment tools.
