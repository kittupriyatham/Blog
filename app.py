"""Thin Flask entrypoint: app setup, the route view functions, and the dev server.

Everything that is not a route lives in `core/` (mirroring the existing core/db/
layout - one package folder per concern, each with an `__init__.py` that is the
package's public API):

    core/config/       env vars + constants (SECRET_KEY, MEDIA_FOLDER, ...)
    core/providers/    storage backends (local vs cloud) for media + database
    core/media/        uploads (delegated to the media provider) + media paths
    core/content/      rich text, canonical URLs, shared helpers
    core/analytics/    first-party analytics (write + dashboard reports)
    core/notify/       Telegram notification
    core/syndication/  platform adapters + background runner
    core/db/           MongoEngine connection, schema + models

The route bodies are unchanged: they call those packages through their module
namespaces (media.upload_to_server(...), content.canonical(...), ...).
"""
import datetime
from datetime import timezone
import email.utils
import json
import os
import re
import secrets
import threading
from typing import Any

from dotenv import load_dotenv

# Load environment variables from ".env" (git-ignored) before anything reads them.
# (core.config.settings loads it too, so importing a package directly also works.)
load_dotenv()

from flask import (
    Flask,
    Response,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
    send_from_directory,
)
from flask_wtf.csrf import CSRFProtect

from core import ai, analytics, content, media, syndication
from core.config import (ADMIN_PASSWORD, ADMIN_USERNAME, ANALYTICS_STORE, MEDIA_FOLDER,
                        SECRET_KEY, SITE_URL, UPLOAD_TOKEN, YOUTUBE_CATEGORY, YOUTUBE_VISIBILITY)
from core.db import Comment, Post, IssueReport, connect_db, ensure_schema
from core.notify import auto_register_webhook, handle_webhook_update, notify_telegram
from core.syndication import runner, socialapi_metrics

app = Flask(__name__)
app.secret_key = SECRET_KEY
csrf = CSRFProtect(app)

# --- Database Setup (MongoEngine) ---
# Schema + indexes live in core/db/models.py. connect_db() opens the single
# MongoEngine connection (MONGO_URI, or a local mongod at 127.0.0.1:27017/blog_db)
# and ensure_schema() idempotently creates collections/indexes (replaces
# dbinit.py). The models back pymongo-style collection handles below, so the
# rest of the app keeps working unchanged while Post/Comment/AnalyticsEvent own
# the schema - including the `syndications` field that drives "Also published on".
connect_db()
ensure_schema()
posts_collection = Post._get_collection()
comments_collection = Comment._get_collection()
issues_collection = IssueReport._get_collection()

# Wire the moved pieces into the app object: the rich_text template filter, the
# canonical/site_url context processor, and the syndication background worker.
content.register(app)
content.register_urls(app)
runner.start_worker()

# Automatically register Telegram webhook on startup in the background
threading.Thread(target=auto_register_webhook, daemon=True).start()

# ---------------------------------------------------------------------------
# Routes — Public
# ---------------------------------------------------------------------------

@app.route("/pinterest-7e38d.html")
def pinterest_verify():
    repo_root = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(repo_root, "pinterest-7e38d.html")


@app.route("/media/<path:filename>")
def serve_media(filename):
    # Tolerate callers that pass a full "/media/..." path into url_for.
    filename = filename.replace("/media/", "").lstrip("/")
    return send_from_directory(MEDIA_FOLDER, filename)


@csrf.exempt
@app.route("/upload_media", methods=["POST"])
def upload_media():
    """Store an uploaded file in media/ and return its path.

    Named like every other upload - `media_<hash of post id>.<ext>` - and the
    original filename is discarded (only its extension survives). Pass `post_id`
    to attach the file to a post; omit it and one is generated.

    Auth: a logged-in admin session, or the X-Upload-Token header matching
    UPLOAD_TOKEN. CSRF is exempt so scripts can post here; the token (or the
    session) is what protects it.

    Form fields: file (or media), optional post_id. Returns JSON:
        {"status": "success", "post_id": ..., "url": "/media/media_<hash>.<ext>", "name": ...}
    """
    if not media.upload_authorized():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    f = request.files.get("file") or request.files.get("media")
    if not f or not f.filename:
        return jsonify({"status": "error", "message": "No file provided."}), 400
    if not media.allowed_file(f.filename):
        return jsonify({"status": "error", "message": "Unsupported file type."}), 400

    post_id = request.form.get("post_id", "").strip() or media.generate_post_id()
    url = media.upload_to_server(f, media.media_stem(post_id), set())
    return jsonify({"status": "success", "post_id": post_id,
                    "url": url, "name": url.rsplit("/", 1)[-1]})

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    tag = request.args.get("tag", "").strip()
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    per_page = 6

    query = {"$or": [{"status": "published"}, {"status": {"$exists": False}}]}
    if tag:
        query = {"$and": [query, {"tags": tag}]}
    all_docs = list(posts_collection.find(query).sort("timestamp", -1))

    for doc in all_docs:
        if "blocks" in doc:
            text_parts = []
            media_paths = []
            for b in doc["blocks"]:
                if b.get("type") == "text" and b.get("content"):
                    text_parts.append(b.get("content").strip())
                elif b.get("type") == "media" and b.get("media_paths"):
                    media_paths.extend(b.get("media_paths"))
            doc["content"] = "\n\n".join(text_parts)
            doc["media_paths"] = media_paths

    by_id = {p["post_id"]: p for p in all_docs}
    feed_posts = [p for p in all_docs if p.get("type", "post") != "article"]

    if q:
        ql = q.lower()
        feed_posts = [p for p in feed_posts
                      if ql in (p.get("content") or "").lower() or ql in (p.get("title") or "").lower()]

    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    for p in feed_posts:
        content = p.get("content", "")
        match = pattern.search(content)
        if match and match.group(1) in by_id:
            p["embedded_article"] = by_id[match.group(1)]

    total = len(feed_posts)
    start = (page - 1) * per_page
    page_posts = feed_posts[start:start + per_page]
    articles_list = [p for p in all_docs if p.get("type") == "article"]
    if not session.get("logged_in"):
        analytics.record_analytics({"event": "view", "page": "feed", "path": request.path})
        if request.referrer and analytics._is_external(request.referrer):
            analytics.record_analytics({"event": "reach_in", "page": "feed", "path": request.path})
    return render_template("index.html", posts=page_posts, articles=articles_list, attach_posts=feed_posts[:20],
                           syndication_platforms=syndication.available_platforms(kind="post"),
                           q=q, tag=tag, page=page, has_prev=page > 1, has_next=start + per_page < total, total=total)

@app.route("/tag/<tag>")
def tag_view(tag):
    return redirect(url_for("index", tag=tag))

@app.route("/post/<post_id>")
def post_detail(post_id):
    post = posts_collection.find_one({"post_id": post_id})
    if not post:
        abort(404)
    if post.get("status") == "draft" and not session.get("logged_in"):
        abort(404)

    if "blocks" in post:
        text_parts = [b.get("content", "").strip() for b in post["blocks"] if b.get("type") == "text"]
        media_paths = []
        for b in post["blocks"]:
            if b.get("type") == "media":
                media_paths.extend(b.get("media_paths", []))
        post["content"] = "\n\n".join(text_parts)
        post["media_paths"] = media_paths

    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    match = pattern.search(post.get("content", ""))
    if match:
        linked = posts_collection.find_one({"post_id": match.group(1)})
        if linked:
            post["embedded_article"] = linked

    if not session.get("logged_in"):
        posts_collection.update_one({"post_id": post_id}, {"$inc": {"views": 1}})
        analytics.record_analytics({"event": "view", "post_id": post_id, "type": post.get("type", "post"),
                                    "page": "post", "path": request.path})
        ref = request.referrer or ""
        if ref and analytics._is_external(ref):
            analytics.record_analytics({"event": "reach_in", "post_id": post_id})
        elif ref:
            analytics.record_analytics({"event": "post_opened", "post_id": post_id, "source": ref})
    comments = list(comments_collection.find({"post_id": post_id}).sort("timestamp", 1))
    return render_template("post.html", post=post, comments=comments)

@app.route("/post/<post_id>/comments", methods=["POST"])
def add_comment(post_id):
    post = posts_collection.find_one({"post_id": post_id})
    if not post:
        abort(404)
    target = url_for("post_detail", post_id=post_id) + "#comments"
    if request.form.get("website", "").strip():  # honeypot
        flash("Comment rejected.", "error")
        return redirect(target)
    body = request.form.get("body", "").strip()
    if not body:
        flash("Comment can't be empty.", "error")
        return redirect(target)
    comments_collection.insert_one({
        "post_id": post_id,
        "name": request.form.get("name", "").strip()[:60] or "Anonymous",
        "body": body[:2000],
        "timestamp": content.now_str(),
    })
    analytics.record_analytics({"event": "comments", "post_id": post_id})
    flash("Comment posted.", "success")
    return redirect(target)


@app.route("/article/<article_id>")
def article_detail(article_id):
    article = posts_collection.find_one({"post_id": article_id, "type": "article"})
    if not article:
        abort(404)
    if article.get("status") == "draft" and not session.get("logged_in"):
        abort(404)
    if not session.get("logged_in"):
        posts_collection.update_one({"post_id": article_id}, {"$inc": {"views": 1}})
        analytics.record_analytics({"event": "view", "post_id": article_id, "type": "article",
                                    "page": "article", "path": request.path})
        ref = request.referrer or ""
        if ref and analytics._is_external(ref):
            analytics.record_analytics({"event": "reach_in", "post_id": article_id})
        elif ref:
            analytics.record_analytics({"event": "post_opened", "post_id": article_id, "source": ref})
    return render_template("article.html", post=article)

@csrf.exempt
@app.route("/like/<post_id>", methods=["POST"])
def like_post(post_id):
    reaction = request.args.get("type", "like").lower()
    allowed = {"like", "heart", "fire", "clap", "insightful"}
    if reaction not in allowed:
        reaction = "like"

    update = {"$inc": {f"reactions.{reaction}": 1, "likes": 1}}
    result = posts_collection.find_one_and_update({"post_id": post_id}, update, return_document=True)
    if result:
        reactions_data = result.get("reactions") or {}
        analytics.record_analytics({
            "event": "likes",
            "reaction": reaction,
            "post_id": post_id,
            "count_after": result.get("likes", 0)
        })
        return jsonify({
            "status": "success",
            "likes": result.get("likes", 0),
            "reactions": reactions_data
        })
    return jsonify({"status": "error", "message": "Post not found"}), 404

@csrf.exempt
@app.route("/share/<post_id>", methods=["POST"])
def share_post(post_id):
    method = request.args.get("method") or (request.get_json(silent=True) or {}).get("method") or "copy_link"
    result = posts_collection.find_one_and_update({"post_id": post_id}, {"$inc": {"shares": 1}}, return_document=True)
    if result:
        analytics.record_analytics({
            "event": "shares",
            "post_id": post_id,
            "method": method,
            "count_after": result.get("shares", 0)
        })
        return jsonify({"status": "success", "shares": result.get("shares", 0)})
    return jsonify({"status": "error", "message": "Post not found"}), 404

import hashlib
import hmac

ADMIN_DEVICE_COOKIE = "admin_device_token"

def _admin_device_signature() -> str:
    """Generate a cryptographic HMAC digest tied to SECRET_KEY and ADMIN_USERNAME."""
    key = (SECRET_KEY or "dev-insecure-secret-key").encode("utf-8")
    msg = f"admin-device:{ADMIN_USERNAME}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def is_cert_authorized() -> bool:
    """Device / cert authorization check against HMAC-signed device cookie."""
    try:
        cookie_token = request.cookies.get(ADMIN_DEVICE_COOKIE)
        if cookie_token and hmac.compare_digest(cookie_token, _admin_device_signature()):
            return True
    except Exception:
        pass
    return False


@app.context_processor
def inject_cert_auth():
    return {
        "is_cert_authorized": is_cert_authorized(),
        "is_demo": bool(session.get("is_demo")),
        "current_user": session.get("username", "Admin" if session.get("logged_in") else "")
    }


# ---------------------------------------------------------------------------
# Edge Decoy & Anti-Indexing Hooks
# ---------------------------------------------------------------------------

_ADMIN_PROTECTED_PREFIXES = (
    "/admin",
    "/analytics",
    "/post/editor",
    "/article/create",
    "/edit/",
    "/youtube/",
)


@app.before_request
def intercept_admin_decoy():
    """Intercept unauthorized visits to admin management paths and redirect to /login."""
    path = request.path.rstrip("/") or "/"
    if any(path == prefix or path.startswith(prefix + "/") for prefix in _ADMIN_PROTECTED_PREFIXES):
        if not session.get("logged_in"):
            return redirect(url_for("login"))



@app.after_request
def enforce_security_and_seo_headers(response):
    """Enforce strict anti-indexing on administrative areas and error responses."""
    path = request.path.rstrip("/") or "/"
    is_admin_path = any(path == prefix or path.startswith(prefix + "/") or path.startswith(prefix) for prefix in _ADMIN_PROTECTED_PREFIXES)
    if is_admin_path or response.status_code in (401, 403, 404, 500):
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    return response


# ---------------------------------------------------------------------------
# Global Dynamic Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def handle_404(e):
    return render_template(
        "error.html",
        error_code=404,
        error_title="Page Not Found",
        error_message="The story or resource you are looking for does not exist, has been removed, or is temporarily unavailable.",
    ), 404


@app.errorhandler(403)
def handle_403(e):
    return render_template(
        "error.html",
        error_code=403,
        error_title="Access Forbidden",
        error_message="You do not have permission to access this area.",
    ), 403


@app.errorhandler(500)
def handle_500(e):
    return render_template(
        "error.html",
        error_code=500,
        error_title="Internal Server Error",
        error_message="An unexpected server error occurred while processing your request. Please try again shortly.",
    ), 500


# ---------------------------------------------------------------------------
# Utility Routes — Health Check, Robots, Sitemap & AI Context
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET", "HEAD"])
def health_check():
    """Ultra-lightweight endpoint for external uptime pingers to prevent cold starts."""
    return Response("OK", status=200, mimetype="text/plain")


@app.route("/robots.txt")
def robots_txt():
    """Standard robots.txt with dynamic Sitemap URL."""
    base_url = (SITE_URL or request.host_url.rstrip("/")).rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /llms.txt\n"
        "Disallow: /login\n"
        "Disallow: /admin/\n"
        "Disallow: /analytics\n"
        "Disallow: /health\n"
        "Disallow: /static/\n\n"
        f"Sitemap: {base_url}/sitemap.xml\n"
    )
    return Response(body, status=200, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    """Dynamic XML sitemap conforming to sitemaps.org schema 0.9."""
    base_url = (SITE_URL or request.host_url.rstrip("/")).rstrip("/")
    now_iso = content.now_str().split(" ")[0]

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <url>',
        f'    <loc>{base_url}/</loc>',
        f'    <lastmod>{now_iso}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>1.0</priority>',
        '  </url>',
        '  <url>',
        f'    <loc>{base_url}/articles</loc>',
        f'    <lastmod>{now_iso}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>0.8</priority>',
        '  </url>',
        '  <url>',
        f'    <loc>{base_url}/posts</loc>',
        f'    <lastmod>{now_iso}</lastmod>',
        '    <changefreq>daily</changefreq>',
        '    <priority>0.8</priority>',
        '  </url>',
    ]

    # Query published public posts and articles
    try:
        query = {"status": "published"}
        docs = list(posts_collection.find(query).sort("timestamp", -1))
        for doc in docs:
            pid = doc.get("post_id")
            if not pid:
                continue
            item_type = doc.get("type", "post")
            loc = f"{base_url}/article/{pid}" if item_type == "article" else f"{base_url}/post/{pid}"
            ts = doc.get("timestamp") or now_iso
            date_str = ts.split(" ")[0] if " " in ts else ts[:10]
            priority = "0.7" if item_type == "article" else "0.6"
            xml_lines.extend([
                '  <url>',
                f'    <loc>{loc}</loc>',
                f'    <lastmod>{date_str}</lastmod>',
                '    <changefreq>monthly</changefreq>',
                f'    <priority>{priority}</priority>',
                '  </url>',
            ])
    except Exception as e:
        print("[sitemap] Failed querying posts:", e)

    xml_lines.append('</urlset>')
    return Response("\n".join(xml_lines), status=200, mimetype="application/xml; charset=utf-8")


def _to_rfc822(ts_str):
    if not ts_str:
        return email.utils.formatdate(usegmt=True)
    try:
        dt = datetime.datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return email.utils.format_datetime(dt)
    except Exception:
        try:
            dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return email.utils.format_datetime(dt)
        except Exception:
            return email.utils.formatdate(usegmt=True)


@app.route("/rss.xml")
@app.route("/feed.xml")
@app.route("/feed")
@app.route("/rss")
def rss_feed():
    """Generate a standard RSS 2.0 XML feed of published posts and articles."""
    base_url = (SITE_URL or request.host_url.rstrip("/")).rstrip("/")

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>Kittu Priyatham</title>',
        f'    <link>{base_url}/</link>',
        '    <description>Personal blog, thoughts on engineering, distributed systems, and POSSE syndication.</description>',
        '    <language>en-us</language>',
        f'    <atom:link href="{base_url}/rss.xml" rel="self" type="application/rss+xml"/>',
    ]

    try:
        query = {"status": "published", "is_demo": {"$ne": True}}
        docs = list(posts_collection.find(query).sort("timestamp", -1).limit(50))

        for doc in docs:
            pid = doc.get("post_id")
            if not pid:
                continue
            item_type = doc.get("type", "post")
            is_article = item_type == "article"
            loc = f"{base_url}/article/{pid}" if is_article else f"{base_url}/post/{pid}"

            text_parts = [b.get("content", "").strip() for b in doc.get("blocks", []) if b.get("type") == "text"]
            body_text = "\n\n".join(p for p in text_parts if p) or (doc.get("content") or "").strip()

            if is_article:
                title = (doc.get("title") or "Article").strip()
            else:
                first_line = body_text.split("\n")[0].strip() if body_text else ""
                title = first_line[:100] if first_line else "Post"

            clean_title = title.replace("]]>", "]]&gt;")
            clean_body = body_text.replace("]]>", "]]&gt;")
            pub_date = _to_rfc822(doc.get("timestamp"))
            author = doc.get("author") or "Kittu Priyatham"

            xml_lines.append('    <item>')
            xml_lines.append(f'      <title><![CDATA[{clean_title}]]></title>')
            xml_lines.append(f'      <link>{loc}</link>')
            xml_lines.append(f'      <guid isPermaLink="true">{loc}</guid>')
            xml_lines.append(f'      <pubDate>{pub_date}</pubDate>')
            xml_lines.append(f'      <author><![CDATA[{author}]]></author>')

            for t in doc.get("tags") or []:
                if t and isinstance(t, str):
                    xml_lines.append(f'      <category><![CDATA[{t.strip()}]]></category>')

            cover = doc.get("cover_image")
            if cover and isinstance(cover, str):
                cover_url = f"{base_url}{cover}" if cover.startswith("/") else cover
                xml_lines.append(f'      <enclosure url="{cover_url}" length="0" type="image/jpeg"/>')

            xml_lines.append(f'      <description><![CDATA[{clean_body}]]></description>')
            xml_lines.append('    </item>')

    except Exception as e:
        print("[rss] Error generating feed:", e)

    xml_lines.append('  </channel>')
    xml_lines.append('</rss>')

    return Response("\n".join(xml_lines), status=200, mimetype="application/rss+xml; charset=utf-8")


@app.route("/llms.txt")
def llms_txt():
    """Structured markdown document for AI agents and LLMs (llmstxt.org standard)."""
    base_url = (SITE_URL or request.host_url.rstrip("/")).rstrip("/")
    lines = [
        "# Kittu Priyatham's Personal Publication",
        "",
        "> Personal technical blog, long-form articles, and thoughts on AI, software architecture, and technology.",
        "",
        f"- Canonical Site: {base_url}",
        f"- Author: Kittu Priyatham",
        "",
        "## Core Feeds",
        "",
        f"- [Home]({base_url}/): Latest mixed feed of articles and micro-posts.",
        f"- [Articles]({base_url}/articles): Full-length essays, architecture notes, and in-depth guides.",
        f"- [Posts]({base_url}/posts): Short-form updates, announcements, and notes.",
        "",
        "## Published Content Catalog",
        "",
    ]

    try:
        query = {"status": "published"}
        docs = list(posts_collection.find(query).sort("timestamp", -1))
        if not docs:
            lines.append("No published stories yet.")
        for doc in docs:
            pid = doc.get("post_id")
            if not pid:
                continue
            item_type = doc.get("type", "post")
            title = doc.get("title") or (doc.get("content") or f"Post {pid}")[:60].strip()
            loc = f"{base_url}/article/{pid}" if item_type == "article" else f"{base_url}/post/{pid}"
            date_str = (doc.get("timestamp") or "")[:10]
            summary = (doc.get("content") or "").replace("\n", " ")[:140].strip()
            lines.append(f"- [{title}]({loc}) ({date_str})")
            if summary and item_type == "article":
                lines.append(f"  > {summary}...")
    except Exception as e:
        lines.append(f"- Error loading catalog: {e}")

    lines.append("")
    resp = Response("\n".join(lines), status=200, mimetype="text/markdown; charset=utf-8")
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp


# ---------------------------------------------------------------------------
# Routes — Admin
# ---------------------------------------------------------------------------

@app.route("/admin/unlock", methods=["GET"])
def admin_unlock():
    """Emergency device bootstrap: if secret key or upload token or admin password matches,
    issue the admin device cookie and redirect directly to /login.
    """
    token = request.args.get("key") or request.args.get("token") or ""
    if token and (
        (SECRET_KEY and hmac.compare_digest(token, SECRET_KEY))
        or (UPLOAD_TOKEN and hmac.compare_digest(token, UPLOAD_TOKEN))
        or (ADMIN_PASSWORD and hmac.compare_digest(token, ADMIN_PASSWORD))
    ):
        resp = make_response(redirect(url_for("login")))
        resp.set_cookie(
            ADMIN_DEVICE_COOKIE,
            _admin_device_signature(),
            max_age=10 * 365 * 24 * 3600,
            httponly=True,
            samesite="Lax",
            secure=True
        )
        flash("Device authorized! You can now log in.", "success")
        return resp
    abort(404)


@app.route("/demo_login", methods=["POST"])
def demo_login():
    """One-click sign-in as Demo Publisher."""
    session.clear()
    session["logged_in"] = True
    session["is_demo"] = True
    session["username"] = "Demo Publisher"
    flash("Welcome to the Publisher Demo! You have full access to drafting, rich blocks, AI studio, and per-platform syndication previews (external syndications are simulated).", "success")
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("index"))
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        if u.lower() == "demo" and p.lower() == "demo":
            session.clear()
            session["logged_in"] = True
            session["is_demo"] = True
            session["username"] = "Demo Publisher"
            flash("Welcome to the Publisher Demo! You have full access to drafting, rich blocks, AI studio, and per-platform syndication previews (external syndications are simulated).", "success")
            return redirect(url_for("index"))
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["is_demo"] = False
            session["username"] = ADMIN_USERNAME
            session["logged_in"] = True
            resp = make_response(redirect(url_for("index")))
            # Permanently mark this specific browser as the Admin's device (10 years)
            resp.set_cookie(
                ADMIN_DEVICE_COOKIE,
                _admin_device_signature(),
                max_age=10 * 365 * 24 * 3600,
                httponly=True,
                samesite="Lax",
                secure=True
            )
            return resp
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


def _demo_syndication_url(platform, kind, doc_id):
    """Generate canonical simulated preview link for demo mode syndications.
    Format: %blog-site%/example/<platform>/<post/article>_<id>
    """
    base = (SITE_URL or "").rstrip("/")
    if not base:
        try:
            base = request.host_url.rstrip("/")
        except Exception:
            base = "https://blog.potluri-krishna-priyatham.tech"
    doc_id_str = str(doc_id).strip()
    if doc_id_str.startswith(f"{kind}_"):
        target = doc_id_str
    else:
        target = f"{kind}_{doc_id_str}"
    return f"{base}/example/{platform}/{target}"


@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if not session.get("logged_in"): return redirect(url_for("login"))
    if request.method == "GET":
        published_articles = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
        published_posts = list(posts_collection.find({"type": "post", "status": "published"}).sort("timestamp", -1).limit(20))
        return render_template("post_editor.html", post=None, content="", media_paths=[], articles=published_articles, attach_posts=published_posts, syndication_platforms=syndication.available_platforms(kind="post"))
    # Named `body` (not `content`) so the core.content package stays reachable.
    body = request.form.get("content", "").strip()
    media_files = request.files.getlist("media")
    platforms = request.form.getlist("platforms")
    youtube_meta = _parse_youtube_meta(request.form.get("youtube_meta"))
    custom_syndications = _parse_custom_syndications(request.form.get("custom_syndications"))
    # Text is required only when the post carries no video and YouTube is not
    # selected: a video-only post (the typical YouTube case) is valid, and its
    # details come from the inline panel.
    if not body and not _has_video_upload(media_files) and "youtube" not in platforms:
        flash("Content is required.", "error")
        return redirect(url_for("index"))
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    # The id must exist before uploads, so media can be named after it.
    post_id = media.generate_post_id()
    taken: set = set()
    stem = media.media_stem(post_id)
    media_urls = [media.upload_to_server(f, stem, taken) for f in media_files if f and media.allowed_file(f.filename)]
    # An empty text block is never stored: a media-only post should stay media-only.
    blocks: list[dict] = []
    if body:
        blocks.append({"type": "text", "content": body})
    if media_urls:
        blocks.append({"type": "media", "media_paths": media_urls})
    new_post: dict[str, Any] = {
        "post_id": post_id, "type": "post",
        "blocks": blocks, "tags": tags,
        "timestamp": content.now_str(),
        "status": "published", "likes": 0, "views": 0,
        "is_demo": bool(session.get("is_demo")),
        "author": "Demo Publisher" if session.get("is_demo") else "Kittu Priyatham"
    }
    # Metadata collected in the composer's YouTube panel, stored as doc["youtube"]
    # so the hand-off page arrives prefilled (no re-entry).
    if youtube_meta:
        new_post["youtube"] = youtube_meta
    if custom_syndications:
        new_post["custom_syndications"] = custom_syndications
    posts_collection.insert_one(new_post)
    if session.get("is_demo"):
        demo_syndications = []
        for p in platforms:
            if p == "youtube":
                continue
            demo_syndications.append({
                "platform": p,
                "label": syndication.label_for(p),
                "url": _demo_syndication_url(p, "post", post_id),
                "remote_id": f"demo_{p}_{post_id}",
                "status": "posted",
                "posted_at": content.now_str(),
                "error": None
            })
        if demo_syndications:
            posts_collection.update_one({"post_id": post_id}, {"$set": {"syndications": demo_syndications}})
        flash("Post published in Demo Mode! Simulated syndications applied so you can experience POSSE.", "success")
        return redirect(url_for("index"))
    # YouTube is published from its own page (/youtube/<post_id>), where the video
    # and all the metadata live. Publishing it in this batch would send a
    # metadata-less post, so it is deferred and the author is taken straight to
    # that page - the attached video travels with the post and is the source used
    # there (see syndication.video_for / attached_video_for).
    runner.enqueue_syndication(post_id, content.canonical("post_detail", post_id=post_id),
                               [p for p in platforms if p != "youtube"])
    if "youtube" in platforms:
        flash("Post published - add the YouTube details and publish from here.", "success")
        return redirect(url_for("youtube_editor", post_id=post_id))
    flash("Post published to cloud!", "success")
    return redirect(url_for("index"))

@app.route("/edit_post/<post_id>", methods=["GET"])
def edit_post(post_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    post = posts_collection.find_one({"post_id": post_id})
    if not post: abort(404)
    if session.get("is_demo") and not post.get("is_demo"):
        flash("Demo account cannot edit the author's original posts. You can create your own posts!", "error")
        return redirect(url_for("index"))
    text, media_paths = content.post_text_and_media(post)
    published_articles = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
    published_posts = list(posts_collection.find({"type": "post", "status": "published"}).sort("timestamp", -1).limit(20))
    return render_template("post_editor.html", post=post, content=text, media_paths=media_paths, articles=published_articles, attach_posts=published_posts,
                           syndication_platforms=syndication.available_platforms(kind="post"),
                           youtube_meta=(post.get("youtube") or {}))

@app.route("/api/save_post", methods=["POST"])
def api_save_post():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    # Named `body` (not `content`) so the core.content package stays reachable.
    body = request.form.get("content", "").strip()
    action = request.form.get("action", "draft")
    post_id = request.form.get("post_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    platforms = request.form.getlist("platforms")
    youtube_meta = _parse_youtube_meta(request.form.get("youtube_meta"))
    existing = posts_collection.find_one({"post_id": post_id}) if post_id else None
    if session.get("is_demo") and existing and not existing.get("is_demo"):
        return jsonify({"status": "error", "message": "Demo mode cannot edit author's original posts. You can create your own!"}), 403
    # Gather the pending uploads up front: they decide both whether text is
    # required and what gets stored.
    try:
        new_files = int(request.form.get("new_files", "0") or 0)
    except (TypeError, ValueError):
        new_files = 0
    pending = [f for f in (request.files.get(f"file_{i}") for i in range(new_files)) if f and f.filename]
    # Text is required only when the post carries no video and YouTube is not
    # selected: a video-only post (the typical YouTube case) is valid.
    if action == "publish" and not body and not _has_video_upload(pending) and "youtube" not in platforms:
        return jsonify({"status": "error", "message": "Content is required to publish."}), 400
    existing = posts_collection.find_one({"post_id": post_id}) if post_id else None
    try:
        keep_media = json.loads(request.form.get("keep_media", "[]"))
    except (TypeError, ValueError):
        keep_media = []
    # Resolve the id before uploads, so media is named after it.
    if not post_id:
        post_id = media.generate_post_id()
    taken: set = set()
    stem = media.media_stem(post_id)
    media_paths = list(keep_media)
    skipped = []
    for f in pending:
        if media.allowed_file(f.filename): media_paths.append(media.upload_to_server(f, stem, taken))
        else: skipped.append(f.filename)
    # An empty text block is never stored: a media-only post stays media-only.
    blocks: list[dict] = []
    if body:
        blocks.append({"type": "text", "content": body})
    if media_paths:
        blocks.append({"type": "media", "media_paths": media_paths})
    status = "published" if action == "publish" else "draft"
    current_time = content.now_str()
    update_data = {
        "post_id": post_id, "type": "post", "blocks": blocks, "status": status, "tags": tags,
        "timestamp": current_time if status == "published" else (existing.get("timestamp", current_time) if existing else current_time),
        "likes": existing.get("likes", 0) if existing else 0,
        "views": existing.get("views", 0) if existing else 0,
        "is_demo": bool(session.get("is_demo")),
        "author": "Demo Publisher" if session.get("is_demo") else "Kittu Priyatham"
    }
    # Metadata collected in the editor's YouTube panel -> doc["youtube"] (merged so
    # a dedicated upload's `video` key survives an edit).
    if youtube_meta:
        update_data["youtube"] = _merge_youtube_meta(existing, youtube_meta)
    if custom_syndications:
        update_data["custom_syndications"] = custom_syndications
    posts_collection.update_one({"post_id": post_id}, {"$set": update_data}, upsert=True)
    response = {"status": "success", "post_id": post_id, "skipped": skipped}
    if status == "published":
        if session.get("is_demo"):
            demo_syndications = []
            for p in platforms:
                if p == "youtube":
                    continue
                demo_syndications.append({
                    "platform": p,
                    "label": syndication.label_for(p),
                    "url": _demo_syndication_url(p, "post", post_id),
                    "remote_id": f"demo_{p}_{post_id}",
                    "status": "posted",
                    "posted_at": content.now_str(),
                    "error": None
                })
            if demo_syndications:
                posts_collection.update_one({"post_id": post_id}, {"$set": {"syndications": demo_syndications}})
        else:
            # Same deferral as create_post: YouTube's video + metadata are completed on
            # /youtube/<post_id>, so publishing it here would send a metadata-less
            # post. Tell the editor to navigate to that page instead (its panel values
            # are already stored, so nothing is re-entered there).
            runner.enqueue_syndication(post_id, content.canonical("post_detail", post_id=post_id),
                                       [p for p in platforms if p != "youtube"])
            if "youtube" in platforms:
                response["redirect"] = url_for("youtube_editor", post_id=post_id)
    return jsonify(response)

@app.route("/articles")
def articles_dashboard():
    published = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
    drafts = []
    if session.get("logged_in"):
        drafts = list(posts_collection.find({"type": "article", "status": "draft"}).sort("timestamp", -1))
    return render_template("articles.html", published=published, drafts=drafts)



@app.route("/posts")
def posts_dashboard():
    all_docs = list(posts_collection.find().sort("timestamp", -1))
    all_articles = {p["post_id"]: p for p in all_docs if p.get("type") == "article"}
    posts_list = [p for p in all_docs if p.get("type", "post") != "article"]

    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    for p in posts_list:
        if "blocks" in p:
            text_parts = [b.get("content", "").strip() for b in p["blocks"] if b.get("type") == "text"]
            media_paths = []
            for b in p["blocks"]:
                if b.get("type") == "media":
                    media_paths.extend(b.get("media_paths", []))
            p["content"] = "\n\n".join(text_parts)
            p["media_paths"] = media_paths

        match = pattern.search(p.get("content", ""))
        if match and match.group(1) in all_articles:
            p["embedded_article"] = all_articles[match.group(1)]

    published = [p for p in posts_list if p.get("status", "published") != "draft"]
    drafts = []
    if session.get("logged_in"):
        drafts = [p for p in posts_list if p.get("status") == "draft"]
    return render_template("posts.html", published=published, drafts=drafts)



# --- YouTube upload ---------------------------------------------------------
# The common YouTube categories as (id, name). "22" (People & Blogs) is the
# default from core.config.YOUTUBE_CATEGORY; so is the visibility, from
# YOUTUBE_VISIBILITY. Both are only form defaults - the saved value wins.
YOUTUBE_CATEGORIES = [
    ("1", "Film & Animation"), ("2", "Autos & Vehicles"), ("10", "Music"),
    ("15", "Pets & Animals"), ("17", "Sports"), ("19", "Travel & Events"),
    ("20", "Gaming"), ("22", "People & Blogs"), ("23", "Comedy"),
    ("24", "Entertainment"), ("25", "News & Politics"), ("26", "Howto & Style"),
    ("27", "Education"), ("28", "Science & Technology"), ("29", "Nonprofits & Activism"),
]


@app.context_processor
def _youtube_panel_defaults():
    """YouTube form defaults for the composers' inline panel.

    _syndication_options.html (included by the feed composer, the post editor and
    the article editor) renders the same category list / defaults as the dedicated
    /youtube page. Injecting them globally keeps those renders from having to
    thread the values through _youtube_panel.html.
    """
    return {
        "youtube_categories": YOUTUBE_CATEGORIES,
        "youtube_default_category": YOUTUBE_CATEGORY,
        "youtube_default_visibility": YOUTUBE_VISIBILITY,
    }


def _youtube_meta_from(values):
    """Normalise YouTube fields into the stored doc["youtube"] dict.

    Shared by the dedicated /youtube page (`values` = request.form) and the
    composers (`values` = the parsed `youtube_meta` JSON), so the field names and
    defaults can never drift apart. `values` only needs a `.get`.
    """
    def field(name):
        val = values.get(name, "")
        if isinstance(val, bool):
            return "1" if val else ""
        return val.strip() if isinstance(val, str) else ("" if val is None else str(val).strip())

    def checked(name):
        val = values.get(name, "")
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("1", "true", "on", "yes")

    return {
        "title": field("title")[:100],
        "description": field("description"),
        "tags": [t.strip() for t in field("tags").split(",") if t.strip()],
        "category_id": field("category_id") or YOUTUBE_CATEGORY,
        "visibility": field("visibility") or YOUTUBE_VISIBILITY,
        "made_for_kids": checked("made_for_kids"),
        "embeddable": checked("embeddable"),
        "license": field("license"),
        "public_stats_viewable": checked("public_stats_viewable"),
        "default_language": field("default_language"),
        "recording_date": field("recording_date"),
        "contains_synthetic_media": checked("contains_synthetic_media"),
        "notify_subscribers": checked("notify_subscribers"),
        "playlist_id": field("playlist_id"),
        "publish_at": field("publish_at"),
        "first_comment": field("first_comment"),
    }


def _parse_youtube_meta(raw):
    """The inline panel's JSON from a composer, or {} when absent/invalid."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return _youtube_meta_from(data)


def _parse_custom_syndications(raw):
    """Parse custom per-platform syndication text overrides JSON."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            cleaned[k.strip().lower()] = v.strip()
    return cleaned


def _has_video_upload(files):
    """True when any pending upload is a video (mirrors syndication.VIDEO_EXTENSIONS)."""
    for f in files or []:
        name = getattr(f, "filename", "") or ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext in syndication.VIDEO_EXTENSIONS:
            return True
    return False


def _merge_youtube_meta(existing, youtube_meta):
    """Existing doc["youtube"] updated with freshly collected panel values.

    Merging (rather than replacing) keeps a dedicated /youtube upload's `video`
    key when a composer re-saves the panel.
    """
    merged = dict((existing or {}).get("youtube") or {})
    merged.update(youtube_meta or {})
    return merged


def _clear_youtube_videos(post_id):
    """Remove any existing `video_<post_id>.*` so a re-upload replaces it."""
    prefix = "video_%s." % post_id
    try:
        names = os.listdir(syndication.VIDEO_DIR)
    except FileNotFoundError:
        return
    for name in names:
        if name.startswith(prefix):
            try:
                os.remove(os.path.join(syndication.VIDEO_DIR, name))
            except OSError:
                pass


def _youtube_default_title(post):
    """Seed the YouTube title from the post so the form is not blank on arrival."""
    title = (post.get("title") or "").strip()
    if title:
        return title[:100]
    for block in post.get("blocks", []) or []:
        if block.get("type") == "text":
            first = ((block.get("content") or "").strip().splitlines() or [""])[0].strip()
            if first:
                return first[:100]
    return ""


@app.route("/youtube/<post_id>", methods=["GET"])
def youtube_editor(post_id):
    """Dedicated YouTube upload page: every field YouTube asks for, plus a video."""
    if not session.get("logged_in"): return redirect(url_for("login"))
    post = posts_collection.find_one({"post_id": post_id})
    if not post: abort(404)
    # The video to publish: a file uploaded on this page wins, otherwise a video
    # already attached to the post (composer/editor) is used as-is, so the author
    # never has to upload the same file a second time.
    dedicated = syndication.video_path_for(post_id)
    attached = None if dedicated else syndication.attached_video_for(post)
    if dedicated:
        video_name = os.path.basename(dedicated)
        video_url = url_for("static", filename="video/" + video_name)
    elif attached:
        video_name = attached.rsplit("/", 1)[-1]
        video_url = attached
    else:
        video_name = None
        video_url = None
    youtube_meta = dict(post.get("youtube") or {})
    if not youtube_meta.get("title"):
        youtube_meta["title"] = _youtube_default_title(post)
    return render_template("youtube.html", post=post,
                           youtube=youtube_meta,
                           video=video_name, video_url=video_url,
                           video_attached=bool(attached),
                           categories=YOUTUBE_CATEGORIES,
                           default_category=YOUTUBE_CATEGORY,
                           default_visibility=YOUTUBE_VISIBILITY)


@app.route("/youtube/<post_id>", methods=["POST"])
def youtube_save(post_id):
    """Store the YouTube metadata (+ an optional video), and publish on request."""
    if not session.get("logged_in"): return redirect(url_for("login"))
    post = posts_collection.find_one({"post_id": post_id})
    if not post: abort(404)

    # Built from `request.form` with the SAME normalisation the composers use for
    # their inline-panel JSON (_youtube_meta_from), so the stored doc["youtube"]
    # shape is identical whichever page collected the values.
    youtube = _youtube_meta_from(request.form)
    title = youtube["title"]

    # A new upload replaces any previous video for this post.
    video_file = request.files.get("video")
    if video_file and video_file.filename:
        ext = video_file.filename.rsplit(".", 1)[-1].lower() if "." in video_file.filename else ""
        if ext not in syndication.VIDEO_EXTENSIONS:
            flash("Unsupported video type '.%s' - use one of: %s."
                  % (ext, ", ".join(sorted(syndication.VIDEO_EXTENSIONS))), "error")
            return redirect(url_for("youtube_editor", post_id=post_id))
        os.makedirs(syndication.VIDEO_DIR, exist_ok=True)
        _clear_youtube_videos(post_id)
        name = "video_%s.%s" % (post_id, ext)
        video_file.save(os.path.join(syndication.VIDEO_DIR, name))
        youtube["video"] = name

    previous = post.get("youtube") or {}
    if "video" not in youtube and previous.get("video"):
        youtube["video"] = previous["video"]

    posts_collection.update_one({"post_id": post_id}, {"$set": {"youtube": youtube}})

    if request.form.get("action") == "publish":
        if not title:
            flash("A YouTube title is required to publish.", "error")
            return redirect(url_for("youtube_editor", post_id=post_id))
        if not syndication.video_for(post):
            flash("Add a video file before publishing to YouTube.", "error")
            return redirect(url_for("youtube_editor", post_id=post_id))
        if post.get("type") == "article":
            url = content.canonical("article_detail", article_id=post_id)
        else:
            url = content.canonical("post_detail", post_id=post_id)
        runner.enqueue_syndication(post_id, url, ["youtube"])
        flash("Queued a YouTube publish for %s - watch the post page for the result." % post_id, "success")
    else:
        flash("YouTube details saved.", "success")
    return redirect(url_for("youtube_editor", post_id=post_id))


@app.route("/create_article", methods=["GET"])
def create_article():
    if not session.get("logged_in"): return redirect(url_for("login"))
    return render_template("create_article.html", article=None, syndication_platforms=syndication.available_platforms(kind="article"))

@app.route("/edit_article/<article_id>", methods=["GET"])
def edit_article(article_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    article = posts_collection.find_one({"post_id": article_id, "type": "article"})
    if not article: abort(404)
    if session.get("is_demo") and not article.get("is_demo"):
        flash("Demo users cannot edit original author articles. You can edit your own demo articles!", "error")
        return redirect(url_for("articles_dashboard"))
    return render_template("create_article.html", article=article,
                           syndication_platforms=syndication.available_platforms(kind="article"),
                           youtube_meta=(article.get("youtube") or {}))

@app.route("/api/save_article", methods=["POST"])
def api_save_article():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    title, action, article_id = request.form.get("title", "").strip(), request.form.get("action", "draft"), request.form.get("article_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    youtube_meta = _parse_youtube_meta(request.form.get("youtube_meta"))
    existing_article = posts_collection.find_one({"post_id": article_id}) if article_id else None
    if session.get("is_demo") and existing_article and not existing_article.get("is_demo"):
        return jsonify({"status": "error", "message": "Demo mode cannot edit author's original articles. You can create your own articles!"}), 403
    # Resolve the final id before uploads, so media is named after it.
    original_id = article_id
    if not article_id:
        article_id = ("article_" if action == "publish" else "draft_") + media.generate_post_id()
    elif action == "publish" and article_id.startswith("draft_"):
        # Promote the stored draft's URL from draft_* to article_* when published.
        article_id = "article_" + media.generate_post_id()
    taken: set = set()
    if existing_article:
        if existing_article.get("cover_image"):
            taken.add(str(existing_article["cover_image"]).split("/")[-1])
        for b in existing_article.get("blocks", []):
            for mp in b.get("media_paths", []):
                taken.add(str(mp).split("/")[-1])
    stem = media.media_stem(article_id)
    skipped = []
    # An explicit Remove clears the saved cover; otherwise a new upload replaces
    # it and no upload keeps whatever was already stored.
    remove_cover = request.form.get("remove_cover", "").strip().lower() in ("1", "true", "on", "yes")
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename:
        if media.allowed_file(cover_file.filename):
            cover_image_url = media.upload_to_server(cover_file, stem, taken)
        else:
            skipped.append(cover_file.filename)
            cover_image_url = existing_article.get("cover_image") if existing_article else None
    elif remove_cover:
        cover_image_url = None
    else:
        cover_image_url = existing_article.get("cover_image") if existing_article else None
    try:
        blocks_meta = json.loads(request.form.get("blocks_meta", "[]"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid blocks_meta"}), 400
    final_blocks = []
    for block in blocks_meta:
        if block.get("type") == "text": final_blocks.append(block)
        elif block.get("type") == "media":
            if block.get("saved_path"): final_blocks.append({"type": "media", "media_paths": [block.get("saved_path")]})
            else:
                f = request.files.get(f"file_{block.get('fileIndex')}")
                if f and media.allowed_file(f.filename): final_blocks.append({"type": "media", "media_paths": [media.upload_to_server(f, stem, taken)]})
                elif f and f.filename: skipped.append(f.filename)
    current_time = content.now_str()
    update_data = {
        "post_id": article_id, "type": "article", "title": title, "cover_image": cover_image_url, "blocks": final_blocks, "tags": tags,
        "status": "published" if action == "publish" else "draft",
        "timestamp": current_time if (action == "publish" and (not existing_article or existing_article.get("status") != "published")) else (existing_article.get("timestamp", current_time) if existing_article else current_time),
        "is_demo": bool(session.get("is_demo")),
        "author": "Demo Publisher" if session.get("is_demo") else "Kittu Priyatham"
    }
    custom_syndications = _parse_custom_syndications(request.form.get("custom_syndications"))
    # Metadata collected in the article editor's YouTube panel -> doc["youtube"].
    if youtube_meta:
        update_data["youtube"] = _merge_youtube_meta(existing_article, youtube_meta)
    if custom_syndications:
        update_data["custom_syndications"] = custom_syndications
    posts_collection.update_one({"post_id": original_id or article_id}, {"$set": update_data}, upsert=True)
    response = {"status": "success", "article_id": article_id, "skipped": skipped}
    if action == "publish":
        platforms = request.form.getlist("platforms")
        if session.get("is_demo"):
            demo_syndications = []
            for p in platforms:
                if p == "youtube":
                    continue
                demo_syndications.append({
                    "platform": p,
                    "label": syndication.label_for(p),
                    "url": _demo_syndication_url(p, "article", article_id),
                    "remote_id": f"demo_{p}_{article_id}",
                    "status": "posted",
                    "posted_at": content.now_str(),
                    "error": None
                })
            if demo_syndications:
                posts_collection.update_one({"post_id": article_id}, {"$set": {"syndications": demo_syndications}})
        else:
            # See create_post: YouTube is completed on its own page, so it is deferred
            # and the author is handed off there (the editor JS navigates to this URL).
            runner.enqueue_syndication(article_id, content.canonical("article_detail", article_id=article_id),
                                       [p for p in platforms if p != "youtube"])
            if "youtube" in platforms:
                response["redirect"] = url_for("youtube_editor", post_id=article_id)
    return jsonify(response)

@app.route("/api/syndication/check", methods=["POST"])
def api_syndication_check():
    if not session.get("logged_in"): return jsonify({"ok": False, "detail": "Unauthorized"}), 401
    s = syndication.get(request.form.get("platform", "linkedin"))
    if not s: return jsonify({"ok": False, "detail": "Unknown platform"}), 404
    return jsonify(s.check())


# ---------------------------------------------------------------------------
# Native In-App AI Studio (Ideation, Conversational Drafting & Formatting)
# ---------------------------------------------------------------------------

@app.route("/ai_studio", methods=["GET"])
def ai_studio():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    post_id = (request.args.get("post_id") or request.args.get("article_id") or request.args.get("id") or "").strip()
    mode = request.args.get("mode", "").strip().lower()
    
    initial_draft = None
    existing_id = None
    
    if post_id:
        existing_doc = posts_collection.find_one({"post_id": post_id})
        if existing_doc:
            existing_id = existing_doc.get("post_id")
            doc_type = existing_doc.get("type", "post")
            mode = mode or doc_type
            
            if doc_type == "article":
                raw_blocks = existing_doc.get("blocks", [])
                text_blocks = []
                for b in raw_blocks:
                    if b.get("type") == "text" and b.get("content"):
                        text_blocks.append({"type": "text", "content": b.get("content")})
                
                initial_draft = {
                    "title": existing_doc.get("title", ""),
                    "tags": existing_doc.get("tags", []),
                    "blocks": text_blocks,
                    "body": ""
                }
            else:
                text, _ = content.post_text_and_media(existing_doc)
                initial_draft = {
                    "title": "",
                    "tags": existing_doc.get("tags", []),
                    "blocks": [],
                    "body": text
                }

    if not mode or mode not in ("post", "article"):
        mode = "post"

    return render_template(
        "ai_studio.html",
        initial_mode=mode,
        initial_draft=initial_draft,
        existing_id=existing_id,
        syndication_platforms=syndication.available_platforms(kind=mode),
        ai_available=ai.is_available()
    )


@app.route("/api/ai/studio/chat", methods=["POST"])
def api_ai_studio_chat():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode", "post").strip().lower()
    if mode not in ("post", "article"):
        mode = "post"
    messages = payload.get("messages", [])
    current_draft = payload.get("current_draft")

    result = ai.chat_turn(mode, messages, current_draft)
    return jsonify({
        "status": "success",
        "reply": result.get("reply", ""),
        "draft": result.get("draft", {})
    })


@app.route("/api/ai/studio/finalize", methods=["POST"])
def api_ai_studio_finalize():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    mode = request.form.get("mode", "post").strip().lower()
    action = request.form.get("action", "draft").strip().lower()
    existing_id = request.form.get("existing_id", "").strip()
    try:
        draft = json.loads(request.form.get("draft", "{}"))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid draft payload"}), 400

    platforms = request.form.getlist("platforms")
    custom_syndications = _parse_custom_syndications(request.form.get("custom_syndications"))
    current_time = content.now_str()
    existing_doc = posts_collection.find_one({"post_id": existing_id}) if existing_id else None
    if session.get("is_demo") and existing_doc and not existing_doc.get("is_demo"):
        return jsonify({"status": "error", "message": "Demo mode cannot edit author's original content. You can draft new posts/articles!"}), 403

    if mode == "article":
        title = (draft.get("title") or "Untitled Article").strip()
        tags = draft.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        
        raw_blocks = draft.get("blocks") or []
        blocks = []
        for b in raw_blocks:
            if isinstance(b, dict) and b.get("content"):
                blocks.append({"type": "text", "content": b.get("content").strip()})
            elif isinstance(b, str) and b.strip():
                blocks.append({"type": "text", "content": b.strip()})
        
        if not blocks and draft.get("body"):
            blocks.append({"type": "text", "content": draft.get("body").strip()})

        if existing_doc and existing_doc.get("blocks"):
            existing_media_blocks = [b for b in existing_doc["blocks"] if b.get("type") == "media"]
            if existing_media_blocks and not any(b.get("type") == "media" for b in blocks):
                blocks.extend(existing_media_blocks)

        if existing_doc:
            article_id = existing_id
            if action == "publish" and article_id.startswith("draft_"):
                article_id = "article_" + media.generate_post_id()
            update_data = {
                "post_id": article_id,
                "type": "article",
                "title": title,
                "blocks": blocks,
                "tags": tags,
                "status": "published" if action == "publish" else "draft",
                "timestamp": current_time if (action == "publish" and existing_doc.get("status") != "published") else existing_doc.get("timestamp", current_time)
            }
            if custom_syndications:
                update_data["custom_syndications"] = custom_syndications
            posts_collection.update_one({"post_id": existing_id}, {"$set": update_data})
        else:
            article_id = ("article_" if action == "publish" else "draft_") + media.generate_post_id()
            doc = {
                "post_id": article_id,
                "type": "article",
                "title": title,
                "cover_image": None,
                "blocks": blocks,
                "tags": tags,
                "status": "published" if action == "publish" else "draft",
                "timestamp": current_time,
                "likes": 0,
                "views": 0,
                "shares": 0,
                "is_demo": bool(session.get("is_demo")),
                "author": "Demo Publisher" if session.get("is_demo") else "Kittu Priyatham"
            }
            posts_collection.insert_one(doc)

        if action == "publish":
            if session.get("is_demo"):
                demo_syndications = []
                for p in platforms:
                    if p == "youtube":
                        continue
                    demo_syndications.append({
                        "platform": p,
                        "label": syndication.label_for(p),
                        "url": _demo_syndication_url(p, "article", article_id),
                        "remote_id": f"demo_{p}_{article_id}",
                        "status": "posted",
                        "posted_at": content.now_str(),
                        "error": None
                    })
                if demo_syndications:
                    posts_collection.update_one({"post_id": article_id}, {"$set": {"syndications": demo_syndications}})
            else:
                runner.enqueue_syndication(
                    article_id,
                    content.canonical("article_detail", article_id=article_id),
                    [p for p in platforms if p != "youtube"]
                )
            redirect_url = url_for("article_detail", article_id=article_id)
        else:
            redirect_url = url_for("edit_article", article_id=article_id)

        return jsonify({
            "status": "success",
            "article_id": article_id,
            "redirect_url": redirect_url
        })

    else:
        body = (draft.get("body") or "").strip()
        tags = draft.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        blocks = [{"type": "text", "content": body}] if body else []
        if existing_doc:
            post_id = existing_id
            if action == "publish" and post_id.startswith("draft_"):
                post_id = media.generate_post_id()
            update_data = {
                "post_id": post_id,
                "type": "post",
                "blocks": blocks,
                "tags": tags,
                "status": "published" if action == "publish" else "draft",
                "timestamp": current_time if (action == "publish" and existing_doc.get("status") != "published") else existing_doc.get("timestamp", current_time)
            }
            if custom_syndications:
                update_data["custom_syndications"] = custom_syndications
            posts_collection.update_one({"post_id": existing_id}, {"$set": update_data})
        else:
            post_id = ("draft_" if action == "draft" else "") + media.generate_post_id()
            doc = {
                "post_id": post_id,
                "type": "post",
                "blocks": blocks,
                "tags": tags,
                "status": "published" if action == "publish" else "draft",
                "timestamp": current_time,
                "likes": 0,
                "views": 0,
                "is_demo": bool(session.get("is_demo")),
                "author": "Demo Publisher" if session.get("is_demo") else "Kittu Priyatham"
            }
            posts_collection.insert_one(doc)

        if action == "publish":
            if session.get("is_demo"):
                demo_syndications = []
                for p in platforms:
                    if p == "youtube":
                        continue
                    demo_syndications.append({
                        "platform": p,
                        "label": syndication.label_for(p),
                        "url": _demo_syndication_url(p, "post", post_id),
                        "remote_id": f"demo_{p}_{post_id}",
                        "status": "posted",
                        "posted_at": content.now_str(),
                        "error": None
                    })
                if demo_syndications:
                    posts_collection.update_one({"post_id": post_id}, {"$set": {"syndications": demo_syndications}})
                flash("Post published in Demo Mode! Simulated syndications applied so you can experience POSSE.", "success")
                redirect_url = url_for("index")
            else:
                runner.enqueue_syndication(
                    post_id,
                    content.canonical("post_detail", post_id=post_id),
                    [p for p in platforms if p != "youtube"]
                )
                flash("Post published to blog and enqueued for syndication!", "success")
                redirect_url = url_for("index")
        else:
            redirect_url = url_for("edit_post", post_id=post_id)

        return jsonify({
            "status": "success",
            "post_id": post_id,
            "redirect_url": redirect_url
        })


# ---------------------------------------------------------------------------
# Telegram Webhook & Cron-Job Health Monitor
# ---------------------------------------------------------------------------

@csrf.exempt
@app.route("/api/telegram/webhook", methods=["POST"])
def telegram_webhook():
    """Inbound webhook handler for Telegram Bot updates.
    Handles two-way issue reporting by replying to bot notification messages.
    """
    payload = request.get_json(force=True, silent=True) or {}
    result = handle_webhook_update(payload)
    return jsonify(result or {"status": "ignored"})


@app.route("/health/syndication", methods=["GET", "HEAD"])
def health_syndication():
    """Health check endpoint for cron-job.org / uptime monitoring.
    - If there are unresolved reported issues (status='open' in IssueReport), returns HTTP 500.
    - If any post in the last 48 hours experienced syndication failure, returns HTTP 500.
    - Otherwise returns HTTP 200 'OK'.
    When cron-job.org receives HTTP 500, it triggers an alert email to the author.
    """
    open_issues = list(issues_collection.find({"status": "open"}))
    
    # Check for recent failed syndications
    cutoff_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    recent_failures = list(posts_collection.find({
        "timestamp": {"$gte": cutoff_str},
        "syndications": {"$elemMatch": {"status": "failed"}}
    }))

    if open_issues or recent_failures:
        issue_msgs = [f"Issue #{i.get('report_id')}: {i.get('text')}" for i in open_issues[:5]]
        failure_msgs = [f"Post {p.get('post_id')} has failed syndication" for p in recent_failures[:5]]
        all_problems = issue_msgs + failure_msgs
        error_body = (
            f"ALERT: Syndication Health Degraded\n"
            f"Open Telegram Issues: {len(open_issues)}\n"
            f"Recent Failed Posts: {len(recent_failures)}\n\n"
            + "\n".join(all_problems)
        )
        # One-shot alert delivery:
        # Mark open issues as 'alerted' (with timestamp) right after returning this 500 error.
        # This guarantees cron-job.org receives the 500 failure and sends your email alert,
        # but the very next cron ping immediately returns 200 OK (error status cleared!).
        now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if open_issues:
            open_ids = [i.get("_id") for i in open_issues if i.get("_id")]
            issues_collection.update_many(
                {"_id": {"$in": open_ids}},
                {"$set": {"status": "alerted", "alerted_at": now_ts}}
            )
        # If there are recent failed syndication posts that haven't been opened on GitHub, create an issue
        try:
            from core import github
            if github.is_configured() and recent_failures:
                for rf in recent_failures:
                    if not rf.get("github_issue_created"):
                        rf_pid = rf.get("post_id")
                        title = f"[Alert] Syndication failure on post {rf_pid}"
                        body = (
                            f"### ⚠️ Syndication Failure Detected\n\n"
                            f"- **Post ID:** `{rf_pid}`\n"
                            f"- **Title:** {rf.get('title') or 'Untitled'}\n"
                            f"- **Timestamp:** `{rf.get('timestamp')}`\n\n"
                            f"#### Syndication details:\n"
                            f"```json\n{json.dumps(rf.get('syndications', []), indent=2)}\n```\n"
                        )
                        github.create_issue_async(title, body, labels=["bug", "syndication-failure"])
                        posts_collection.update_one({"_id": rf["_id"]}, {"$set": {"github_issue_created": True}})
        except Exception as gh_e:
            print("[github] health check issue creation error:", gh_e)
        return Response(error_body, status=500, mimetype="text/plain")

    return Response("OK - All systems operational", status=200, mimetype="text/plain")


@app.route("/api/syndication/retry", methods=["POST"])
def api_syndication_retry():
    """Re-queue failed platforms, triggered from the post/article page.

    Platforms already marked `posted` are filtered out rather than trusted to the
    caller: run_syndication skips them anyway, and this way a retry can never
    duplicate a copy that already went out.
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    post_id = request.form.get("post_id", "").strip()
    doc = posts_collection.find_one({"post_id": post_id})
    if not doc:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    syndications = doc.get("syndications") or []
    posted = {s.get("platform") for s in syndications if s.get("status") == "posted"}
    failed = [s.get("platform") for s in syndications
              if s.get("status") == "failed" and s.get("platform")]
    requested = [p for p in request.form.getlist("platforms") if p]
    platforms = [p for p in (requested or failed) if p not in posted]
    if not platforms:
        return jsonify({"status": "error", "message": "Nothing to retry."}), 400

    if doc.get("type") == "article":
        url = content.canonical("article_detail", article_id=post_id)
    else:
        url = content.canonical("post_detail", post_id=post_id)
    runner.enqueue_syndication(post_id, url, platforms)
    return jsonify({"status": "ok", "platforms": platforms})


@app.route("/api/syndication/validate", methods=["POST"])
def api_syndication_validate():
    """Dry-run a post against each platform's rules.

    Uses SocialAPI's validate endpoint, which applies the same checks as
    publishing but sends nothing - so this can be run as often as needed without
    spending the monthly post allowance. Media is prepared exactly as the real
    publish would, which is what makes the size/aspect fixes verifiable here.
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    post_id = request.form.get("post_id", "").strip()
    doc = posts_collection.find_one({"post_id": post_id})
    if not doc:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    if doc.get("type") == "article":
        url = content.canonical("article_detail", article_id=post_id)
    else:
        url = content.canonical("post_detail", post_id=post_id)

    platforms = [p for p in request.form.getlist("platforms") if p]
    if not platforms:
        platforms = [p["id"] for p in syndication.available_platforms() if p["configured"]]

    base_media = syndication.media_for(doc)
    results = []
    for pid in platforms:
        label = syndication.label_for(pid)
        s = syndication.get(pid)
        if not s or not hasattr(s, "validate"):
            results.append({"platform": pid, "label": label, "supported": False, "valid": None,
                            "errors": [], "warnings": [],
                            "note": "Dry-run validation is only available for SocialAPI platforms."})
            continue
        platform_media = list(base_media)
        if pid in syndication.TEXT_CARD_PLATFORMS and not platform_media:
            try:
                platform_media = [syndication.textcard.write(
                    syndication.compose_text(doc, url, [pid]), MEDIA_FOLDER,
                    doc.get("post_id") or post_id)]
            except Exception as e:
                print("[validate] textcard for %s: %s" % (pid, e))
        try:
            res = s.validate(syndication.compose_text(doc, url, [pid]), url, platform_media, doc)
            results.append({"platform": pid, "label": label, "supported": True,
                            "valid": res.get("valid"), "errors": res.get("errors") or [],
                            "warnings": res.get("warnings") or []})
        except Exception as e:
            results.append({"platform": pid, "label": label, "supported": True, "valid": False,
                            "errors": [{"message": str(e)[:300]}], "warnings": []})
    return jsonify({"status": "ok", "results": results})


# --- Per-platform text preview ---------------------------------------------
# Publishing composes the post text once per platform (`compose_text(doc, url,
# [pid])`) and rewrites it down when it overruns that platform's limit. The
# editor's live counter only shows the character count, so the author cannot see
# what each platform will actually receive. These helpers back
# /api/syndication/preview, which runs the SAME composition on the editor's
# unsaved content - nothing is stored and nothing is sent.

def _preview_doc(kind, body_text, title, doc_id):
    """A transient, unsaved doc shaped like the one compose_text() reads."""
    if kind == "article":
        return {"post_id": doc_id or None, "type": "article",
                "title": (title or "").strip(), "blocks": []}
    return {"post_id": doc_id or None, "type": "post",
            "blocks": [{"type": "text", "content": body_text or ""}]}


def _preview_body(doc):
    """The `body` compose_text() derives from `doc` (kept in step with it).

    Only used to decide whether composition had to shorten the text - the text
    itself always comes from compose_text(), so a change there is still honoured.
    """
    if doc.get("type") == "article":
        body = (doc.get("title") or "New article").strip()
    else:
        parts = [b.get("content", "").strip() for b in doc.get("blocks", []) if b.get("type") == "text"]
        body = "\n\n".join(p for p in parts if p) or "New post"
    return body.replace("\r\n", "\n").replace("\r", "\n")


def _preview_url(kind, doc_id):
    """Canonical link the preview reserves room for.

    The real id is used when editing; a placeholder of the same 8-character
    length (see content.syndication_link_reserve) stands in for a new doc, so the
    preview reserves the same link length the editor's live counter does.
    """
    if kind == "article":
        return content.canonical("article_detail", article_id=doc_id or ("article_" + "x" * 8))
    return content.canonical("post_detail", post_id=doc_id or ("x" * 8))


def _preview_shortened(body, url, limit):
    """True when compose_text() had to condense or trim `body` to fit `limit`.

    Mirrors the limit/suffix arithmetic in syndication.compose_text exactly, so a
    row can be tagged "rewritten" without the model having changed the text.
    """
    if limit is None:
        return False
    suffix = ("\n\n" + url) if (url and syndication.is_public_url(url)) else ""
    room = limit - len(suffix)
    return len(body) > max(room, 0)


@csrf.exempt
@app.route("/api/syndication/preview", methods=["POST"])
def api_syndication_preview():
    """Preview, per platform, the exact text that would be published.

    Accepts the editor's current (unsaved) draft as form fields:
        kind      "post" (default) or "article"
        content   the post body / article body (also accepts `text`)
        title     the article title (articles compose from the title)
        tags      comma-separated tags (echoed back; not part of the text)
        post_id / article_id   the doc id when editing, for the canonical link

    Returns {"status": "ok", "kind": ..., "tags": [...], "results": [per platform]}
    where each result is {platform, label, limit, text, length, rewritten,
    configured} (+ "error" when that platform alone failed). It composes through
    the same syndication.compose_text() the publisher uses, so a platform whose
    limit is exceeded comes back rewritten/trimmed and one that fits is
    unchanged. Nothing is stored and nothing is sent; a failure for one platform
    is reported in its own row and never fails the response.
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    kind = (request.form.get("kind") or "").strip().lower()
    if kind not in ("post", "article"):
        kind = "post"
    # Named `body_text` (not `content`) so the core.content package stays reachable.
    body_text = request.form.get("content")
    if body_text is None:
        body_text = request.form.get("text", "")
    title = request.form.get("title", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    doc_id = (request.form.get("post_id") or request.form.get("article_id") or "").strip()

    doc = _preview_doc(kind, body_text, title, doc_id)
    url = _preview_url(kind, doc_id)
    body = _preview_body(doc)

    results = []
    for p in syndication.available_platforms(kind=kind):
        pid = p["id"]
        limit = p.get("limit")
        row = {"platform": pid, "label": p["label"], "limit": limit,
               "configured": p.get("configured", False),
               "text": "", "length": 0, "rewritten": False}
        try:
            text = syndication.compose_text(doc, url, [pid])
            row["text"] = text
            row["length"] = len(text)
            row["rewritten"] = _preview_shortened(body, url, limit)
        except Exception as e:  # one platform must never break the whole preview
            row["error"] = str(e)[:300]
        results.append(row)
    return jsonify({"status": "ok", "kind": kind, "tags": tags, "results": results})


@app.route("/api/syndication/status/<post_id>")
def api_syndication_status(post_id):
    """Per-platform syndication state, polled by the retry button.

    Publishing is handed to a background worker, so the page cannot know the
    outcome from the retry response alone - this reports it once the worker has
    moved each platform out of `queued`.
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    doc = posts_collection.find_one({"post_id": post_id}, {"syndications": 1})
    rows = (doc or {}).get("syndications") or []
    return jsonify({"status": "ok", "syndications": [
        {"platform": s.get("platform"), "label": s.get("label"),
         "state": s.get("status"), "url": s.get("url"), "error": s.get("error")}
        for s in rows]})


@app.route("/api/disconnect_syndication", methods=["POST"])
def api_disconnect_syndication():
    """Disconnect and remove a syndicated social link from a post or article.

    Removes the platform from `post.syndications`, unsets cached metrics from
    `post.platform_metrics`, and deletes associated click-out analytics events.
    Enforces a validation guard (Option C): if the link is not known to be broken
    and force is False, prompts for explicit confirmation before severing.
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    post_id = (request.form.get("post_id") or (request.get_json(silent=True) or {}).get("post_id") or "").strip()
    platform = (request.form.get("platform") or (request.get_json(silent=True) or {}).get("platform") or "").strip().lower()
    force = str(request.form.get("force") or (request.get_json(silent=True) or {}).get("force") or "").lower() in ("1", "true", "yes")

    if not post_id or not platform:
        return jsonify({"status": "error", "message": "Missing post_id or platform"}), 400

    doc = posts_collection.find_one({"post_id": post_id})
    if not doc:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    syndications = doc.get("syndications") or []
    target_syn = next((s for s in syndications if (s.get("platform") or "").lower() == platform), None)
    if not target_syn:
        return jsonify({"status": "error", "message": f"No syndication found for platform '{platform}'"}), 404

    # Validation Guard (Option C):
    cached_metrics = (doc.get("platform_metrics") or {}).get(platform) or {}
    err_text = str(cached_metrics.get("error") or target_syn.get("error") or "").lower()
    is_known_broken = bool("404" in err_text or "not found" in err_text or "revoked" in err_text or cached_metrics.get("is_broken"))

    if not is_known_broken and not force:
        # Check if platform syndicator token or credentials are valid
        if platform == "linkedin":
            try:
                from core.syndication.linkedin import LinkedinSyndicator
                res = LinkedinSyndicator().check()
                if not res.ok:
                    is_known_broken = True
            except Exception:
                pass

        # Also probe the URL directly if available to detect dead/deleted links
        target_url = target_syn.get("url")
        if not is_known_broken and target_url:
            try:
                import urllib.request
                probe_req = urllib.request.Request(
                    target_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(probe_req, timeout=5) as probe_resp:
                    final_url = probe_resp.url or ""
                    # LinkedIn redirects deleted posts to signup/cold-join or login
                    if "linkedin.com" in target_url and ("cold-join" in final_url or "uas/login" in final_url):
                        is_known_broken = True
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 404, 410):
                    is_known_broken = True
            except Exception:
                pass

    if not is_known_broken and not force:
        return jsonify({
            "status": "guard_warning",
            "needs_confirmation": True,
            "message": f"The {platform.capitalize()} link does not currently show an error/404. Are you sure you want to disconnect it from the blog and analytics?"
        }), 200

    # 1. Pull from post.syndications & unset platform_metrics
    posts_collection.update_one(
        {"post_id": post_id},
        {
            "$pull": {"syndications": {"platform": platform}},
            "$unset": {f"platform_metrics.{platform}": ""}
        }
    )

    # 2. Delete click_out tracking events for this post & platform
    try:
        from core.db import AnalyticsEvent
        AnalyticsEvent._get_collection().delete_many({
            "post_id": post_id,
            "platform": platform,
            "event": "click_out"
        })
    except Exception as e:
        print(f"[analytics] Could not purge click_out events: {e}")

    return jsonify({
        "status": "success",
        "message": f"Successfully disconnected {platform.capitalize()} from {post_id}. Link and tracking removed."
    })


@app.route("/api/syndication/link_external", methods=["POST"])
def api_link_external_syndication():
    """Manually link or confirm a published syndication URL (e.g. Medium, LinkedIn, Dev.to).

    Adds or updates `post.syndications` with status='posted' and the provided URL,
    lighting up the platform icon on the blog and enabling click tracking and analytics.
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    post_id = (request.form.get("post_id") or (request.get_json(silent=True) or {}).get("post_id") or "").strip()
    platform = (request.form.get("platform") or (request.get_json(silent=True) or {}).get("platform") or "medium").strip().lower()
    url = (request.form.get("url") or (request.get_json(silent=True) or {}).get("url") or "").strip()

    if not post_id or not url:
        return jsonify({"status": "error", "message": "Missing post_id or url"}), 400

    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"status": "error", "message": "Please enter a valid URL starting with http:// or https://"}), 400

    doc = posts_collection.find_one({"post_id": post_id})
    if not doc:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    label = syndication.label_for(platform) or platform.capitalize()
    new_entry = {
        "platform": platform,
        "label": label,
        "url": url,
        "status": "posted",
        "posted_at": content.now_str(),
        "error": None,
    }

    # Remove existing syndication for this platform if present, then push the new entry
    posts_collection.update_one(
        {"post_id": post_id},
        {"$pull": {"syndications": {"platform": platform}}}
    )
    posts_collection.update_one(
        {"post_id": post_id},
        {
            "$push": {"syndications": new_entry},
            "$unset": {f"platform_metrics.{platform}": ""}
        }
    )

    return jsonify({
        "status": "success",
        "message": f"Successfully linked {label} URL to this post.",
        "syndication": new_entry
    })


@app.route("/example/<platform>/<target>")
def example_syndication_view(platform, target):
    """Interactive preview of how a post or article looks when syndicated to a platform.

    URL format: /example/<platform>/<post/article>_<id>
    """
    clean_target = (target or "").strip()
    kind = "post"
    raw_id = clean_target
    if clean_target.startswith("post_"):
        kind = "post"
        raw_id = clean_target[5:]
    elif clean_target.startswith("article_"):
        kind = "article"
        raw_id = clean_target[8:]
        if raw_id.startswith("article_"):
            raw_id = raw_id[8:]

    doc = posts_collection.find_one({
        "$or": [
            {"post_id": clean_target},
            {"post_id": raw_id},
            {"post_id": f"article_{raw_id}"},
            {"post_id": f"post_{raw_id}"}
        ]
    })

    platform_key = (platform or "").lower().strip()
    platform_label = syndication.label_for(platform_key) if platform_key else (platform or "").title()

    if doc:
        is_article = doc.get("type") == "article"
        if is_article:
            blog_url = content.canonical("article_detail", article_id=doc.get("post_id"))
        else:
            blog_url = content.canonical("post_detail", post_id=doc.get("post_id"))

        custom_syn = doc.get("custom_syndications") or {}
        if custom_syn.get(platform_key):
            post_text = custom_syn[platform_key]
        else:
            post_text = syndication.compose_text(doc, blog_url, platforms=[platform_key] if platform_key else None)

        media_items = syndication.media_for(doc)
        author_name = doc.get("author") or ("Demo Publisher" if doc.get("is_demo") else "Kittu Priyatham")
        timestamp = doc.get("timestamp") or content.now_str()
        post_title = doc.get("title") if is_article else None
    else:
        doc = None
        blog_url = url_for("index", _external=True)
        post_text = f"Exploring automated POSSE syndication to {platform_label}! Publish on your own blog first, then syndicate effortlessly across social channels."
        media_items = []
        author_name = "Demo Publisher"
        timestamp = content.now_str()
        post_title = f"Simulated {kind.title()} Demo"

    return render_template(
        "example_syndication.html",
        platform=platform_key,
        platform_label=platform_label,
        doc=doc,
        kind=kind,
        post_text=post_text,
        media_items=media_items,
        blog_url=blog_url,
        author_name=author_name,
        timestamp=timestamp,
        post_title=post_title
    )


@app.route("/delete/<post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("logged_in"): abort(401)
    doc = posts_collection.find_one({"post_id": post_id})
    if session.get("is_demo") and doc and not doc.get("is_demo"):
        flash("Demo account cannot delete the author's original posts. You can create and delete your own demo posts!", "error")
        return redirect(url_for("articles_dashboard") if doc and doc.get("type") == "article" else url_for("index"))
    posts_collection.delete_one({"post_id": post_id})
    if doc and doc.get("type") == "article":
        flash("Article removed.", "success")
        return redirect(url_for("articles_dashboard"))
    flash("Post removed.", "success")
    return redirect(url_for("index"))

@csrf.exempt
@app.route("/api/analytics", methods=["POST"])
def api_analytics():
    """Collect client-side analytics events (view, shares, clicks, time_spent, ...).

    Public by design: it only records anonymous usage events, no login required.
    CSRF is exempt because visitors aren't logged in; same-origin beacons (the
    only thing that posts here) can't be forged from another origin.
    """
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}
    if not isinstance(payload, dict) or not payload.get("event"):
        return jsonify({"status": "error", "message": "invalid payload"}), 400
    sess = request.cookies.get("__ab_sess")
    if not sess:
        sess = secrets.token_hex(8)
    payload["session_id"] = sess
    analytics.record_analytics(payload)
    resp = make_response("", 204)
    if not request.cookies.get("__ab_sess"):
        resp.set_cookie("__ab_sess", sess, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


@app.route("/admin/analytics")
def analytics_dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    data = analytics.analytics_aggregates(analytics.analytics_events(limit=2000))
    # Social performance rides along in the same `data` blob: the platforms' own
    # likes/comments/views, read from the cache the refresh route below writes
    # (never fetched here - rendering the page must not depend on SocialAPI).
    data["social"] = analytics.social_metrics_summary(
        _syndicated_posts(), configured=socialapi_metrics.metrics_configured())
    return render_template("analytics.html", data=data, analytics_store=ANALYTICS_STORE)


# Columns the social section needs. `blocks` is projected only so an untitled
# post still has a readable label.
_SOCIAL_PROJECTION = {"post_id": 1, "title": 1, "type": 1, "status": 1, "timestamp": 1,
                      "syndications": 1, "platform_metrics": 1, "blocks": 1}

# How many posts one "refresh everything" pass will hit. Each post costs at most
# one SocialAPI read per platform, so this bounds the wait on a synchronous POST.
SOCIAL_REFRESH_LIMIT = 25


def _syndicated_posts(limit=SOCIAL_REFRESH_LIMIT):
    """Posts worth showing in the social section: syndicated, or metrics cached.

    A post with no syndications has no social numbers to show, so it is left out
    rather than rendered as an empty row.
    """
    return list(posts_collection.find(
        {"$or": [{"syndications": {"$exists": True, "$ne": []}},
                 {"platform_metrics": {"$exists": True, "$ne": {}}}]},
        _SOCIAL_PROJECTION,
    ).sort("timestamp", -1).limit(limit))


@app.route("/admin/analytics/refresh", methods=["POST"])
def analytics_refresh_social():
    """Re-read the platforms' own metrics for one post, or for every post.

    Admin-only, and CSRF-protected: CSRFProtect covers the whole app and this
    route is deliberately NOT `@csrf.exempt`, so the browser's `csrf_token()`
    must be present.

    Read-only against SocialAPI (see core/syndication/socialapi_metrics.py). It
    never publishes - the only write is the cache onto the post itself:

        doc["platform_metrics"] = {platform: {likes, comments, views, ...},
                                   "_meta": {fetched_at, errors}}

    Form field: `post_id` (optional - omit to refresh every syndicated post).
    Query/header: `?format=json` or `Accept: application/json` returns the
    summary as JSON instead of redirecting back to the dashboard.
    """
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    post_id = (request.form.get("post_id") or request.args.get("post_id") or "").strip()
    if post_id:
        doc = posts_collection.find_one({"post_id": post_id}, _SOCIAL_PROJECTION)
        if not doc:
            abort(404)
        docs = [doc]
    else:
        docs = _syndicated_posts()

    configured = socialapi_metrics.metrics_configured()
    refreshed = skipped = platform_count = 0
    errors = []
    # With no key every entry would be a "unavailable" placeholder, and caching
    # one over the last good read would destroy real numbers. Report and stop.
    for doc in (docs if configured else []):
        metrics = socialapi_metrics.platform_metrics(doc)
        platforms = {k: v for k, v in metrics.items() if not k.startswith("_")}
        if not platforms:
            # Nothing syndicated to read - writing an empty cache would only make
            # the dashboard claim a refresh happened.
            skipped += 1
            continue
        posts_collection.update_one(
            {"post_id": doc.get("post_id")},
            {"$set": {"platform_metrics": metrics}}
        )
        refreshed += 1
        platform_count += len(platforms)
        for err in (metrics.get("_meta") or {}).get("errors") or []:
            errors.append(err)

    if not configured:
        flash("SOCIALAPI_KEY is not set, so no social metrics could be fetched. "
              "Connect SocialAPI and try again.", "error")
    elif post_id:
        flash("Social metrics for %s: %d platform(s) %s."
              % (post_id, platform_count,
                 "refreshed" if refreshed else "had nothing to fetch"),
              "success" if refreshed else "error")
    else:
        detail = "%d post(s), %d platform(s) refreshed" % (refreshed, platform_count)
        if skipped:
            detail += "; %d skipped (no syndications)" % skipped
        if errors:
            detail += " - %s" % errors[0]
        flash("Social metrics: %s." % detail, "success" if refreshed else "error")

    wants_json = (request.args.get("format") == "json"
                  or "application/json" in (request.headers.get("Accept") or ""))
    if wants_json:
        return jsonify({"status": "ok" if refreshed else "empty",
                        "post_id": post_id or None,
                        "refreshed": refreshed, "skipped": skipped,
                        "configured": configured, "errors": errors[:10]})
    return redirect(url_for("analytics_dashboard"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", 5000)))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
