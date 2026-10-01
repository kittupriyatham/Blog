"""Thin Flask entrypoint: app setup, the route view functions, and the dev server.

Everything that is not a route lives in `src/` (mirroring the existing src/db/
layout - one package folder per concern, each with an `__init__.py` that is the
package's public API):

    src/config/       env vars + constants (SECRET_KEY, MEDIA_FOLDER, ...)
    src/providers/    storage backends (local vs cloud) for media + database
    src/media/        uploads (delegated to the media provider) + media paths
    src/content/      rich text, canonical URLs, shared helpers
    src/analytics/    first-party analytics (write + dashboard reports)
    src/notify/       Telegram notification
    src/syndication/  platform adapters + background runner
    src/db/           MongoEngine connection, schema + models

The route bodies are unchanged: they call those packages through their module
namespaces (media.upload_to_server(...), content.canonical(...), ...).
"""
import json
import os
import re
import secrets

from dotenv import load_dotenv

# Load environment variables from ".env" (git-ignored) before anything reads them.
# (src.config.settings loads it too, so importing a package directly also works.)
load_dotenv()

from flask import (
    Flask,
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

from src import analytics, content, media, syndication
from src.config import ADMIN_PASSWORD, ADMIN_USERNAME, ANALYTICS_STORE, MEDIA_FOLDER, SECRET_KEY
from src.db import Comment, Post, connect_db, ensure_schema
from src.syndication import runner

app = Flask(__name__)
app.secret_key = SECRET_KEY
csrf = CSRFProtect(app)

# --- Database Setup (MongoEngine) ---
# Schema + indexes live in src/db/models.py. connect_db() opens the single
# MongoEngine connection (MONGO_URI, or a local mongod at 127.0.0.1:27017/blog_db)
# and ensure_schema() idempotently creates collections/indexes (replaces
# dbinit.py). The models back pymongo-style collection handles below, so the
# rest of the app keeps working unchanged while Post/Comment/AnalyticsEvent own
# the schema - including the `syndications` field that drives "Also published on".
connect_db()
ensure_schema()
posts_collection = Post._get_collection()
comments_collection = Comment._get_collection()

# Wire the moved pieces into the app object: the rich_text template filter, the
# canonical/site_url context processor, and the syndication background worker.
content.register(app)
content.register_urls(app)
runner.start_worker()

# ---------------------------------------------------------------------------
# Routes — Public
# ---------------------------------------------------------------------------

@app.route("/media/<path:filename>")
def serve_media(filename):
    # Tolerate callers that pass a full "/media/..." path into url_for.
    filename = filename.replace("/media/", "").lstrip("/")
    return send_from_directory(MEDIA_FOLDER, filename)


@app.route("/upload_media", methods=["POST"])
@csrf.exempt
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
    if not post: abort(404)
    if post.get("status") == "draft" and not session.get("logged_in"): abort(404)
    
    if "blocks" in post:
        text_parts = [b.get("content", "").strip() for b in post["blocks"] if b.get("type") == "text"]
        media_paths = []
        for b in post["blocks"]:
            if b.get("type") == "media": media_paths.extend(b.get("media_paths", []))
        post["content"] = "\n\n".join(text_parts)
        post["media_paths"] = media_paths

    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    match = pattern.search(post.get("content", ""))
    if match:
        linked = posts_collection.find_one({"post_id": match.group(1)})
        if linked: post["embedded_article"] = linked

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
    if not post: abort(404)
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
    if not article: abort(404)
    if article.get("status") == "draft" and not session.get("logged_in"): abort(404)
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

@app.route("/like/<post_id>", methods=["POST"])
def like_post(post_id):
    result = posts_collection.find_one_and_update({"post_id": post_id}, {"$inc": {"likes": 1}}, return_document=True)
    if result:
        analytics.record_analytics({"event": "likes", "post_id": post_id, "count_after": result.get("likes", 0)})
        return jsonify({"status": "success", "likes": result.get("likes", 0)})
    return jsonify({"status": "error", "message": "Post not found"}), 404

# ---------------------------------------------------------------------------
# Routes — Admin
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/create_post", methods=["GET", "POST"])
def create_post():
    if not session.get("logged_in"): return redirect(url_for("login"))
    if request.method == "GET":
        published_articles = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
        published_posts = list(posts_collection.find({"type": "post", "status": "published"}).sort("timestamp", -1).limit(20))
        return render_template("post_editor.html", post=None, content="", media_paths=[], articles=published_articles, attach_posts=published_posts, syndication_platforms=syndication.available_platforms(kind="post"))
    # Named `body` (not `content`) so the src.content package stays reachable.
    body = request.form.get("content", "").strip()
    media_files = request.files.getlist("media")
    if not body:
        flash("Content is required.", "error")
        return redirect(url_for("index"))
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    # The id must exist before uploads, so media can be named after it.
    post_id = media.generate_post_id()
    taken: set = set()
    stem = media.media_stem(post_id)
    media_urls = [media.upload_to_server(f, stem, taken) for f in media_files if f and media.allowed_file(f.filename)]
    blocks: list[dict] = [{"type": "text", "content": body}]
    if media_urls:
        blocks.append({"type": "media", "media_paths": media_urls})
    new_post = {
        "post_id": post_id, "type": "post",
        "blocks": blocks, "tags": tags,
        "timestamp": content.now_str(),
        "status": "published", "likes": 0, "views": 0
    }
    posts_collection.insert_one(new_post)
    runner.enqueue_syndication(post_id, content.canonical("post_detail", post_id=post_id),
                               request.form.getlist("platforms"))
    flash("Post published to cloud!", "success")
    return redirect(url_for("index"))

@app.route("/edit_post/<post_id>", methods=["GET"])
def edit_post(post_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    post = posts_collection.find_one({"post_id": post_id})
    if not post: abort(404)
    text, media_paths = content.post_text_and_media(post)
    published_articles = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
    published_posts = list(posts_collection.find({"type": "post", "status": "published"}).sort("timestamp", -1).limit(20))
    return render_template("post_editor.html", post=post, content=text, media_paths=media_paths, articles=published_articles, attach_posts=published_posts, syndication_platforms=syndication.available_platforms(kind="post"))

@app.route("/api/save_post", methods=["POST"])
def api_save_post():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    # Named `body` (not `content`) so the src.content package stays reachable.
    body = request.form.get("content", "").strip()
    action = request.form.get("action", "draft")
    post_id = request.form.get("post_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    if action == "publish" and not body:
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
    try:
        new_files = int(request.form.get("new_files", "0") or 0)
    except (TypeError, ValueError):
        new_files = 0
    for i in range(new_files):
        f = request.files.get(f"file_{i}")
        if f and f.filename:
            if media.allowed_file(f.filename): media_paths.append(media.upload_to_server(f, stem, taken))
            else: skipped.append(f.filename)
    blocks: list[dict] = [{"type": "text", "content": body}]
    if media_paths:
        blocks.append({"type": "media", "media_paths": media_paths})
    status = "published" if action == "publish" else "draft"
    current_time = content.now_str()
    update_data = {
        "post_id": post_id, "type": "post", "blocks": blocks, "status": status, "tags": tags,
        "timestamp": current_time if status == "published" else (existing.get("timestamp", current_time) if existing else current_time),
        "likes": existing.get("likes", 0) if existing else 0,
        "views": existing.get("views", 0) if existing else 0,
    }
    posts_collection.update_one({"post_id": post_id}, {"$set": update_data}, upsert=True)
    if status == "published":
        runner.enqueue_syndication(post_id, content.canonical("post_detail", post_id=post_id), request.form.getlist("platforms"))
    return jsonify({"status": "success", "post_id": post_id, "skipped": skipped})

@app.route("/articles")
def articles_dashboard():
    published = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
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
                if b.get("type") == "media": media_paths.extend(b.get("media_paths", []))
            p["content"] = "\n\n".join(text_parts)
            p["media_paths"] = media_paths

        match = pattern.search(p.get("content", ""))
        if match and match.group(1) in all_articles:
            p["embedded_article"] = all_articles[match.group(1)]
                
    published = [p for p in posts_list if p.get("status", "published") != "draft"]
    drafts = [p for p in posts_list if p.get("status") == "draft"]
    return render_template("posts.html", published=published, drafts=drafts)

@app.route("/create_article", methods=["GET"])
def create_article():
    if not session.get("logged_in"): return redirect(url_for("login"))
    return render_template("create_article.html", article=None, syndication_platforms=syndication.available_platforms(kind="article"))

@app.route("/edit_article/<article_id>", methods=["GET"])
def edit_article(article_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    article = posts_collection.find_one({"post_id": article_id, "type": "article"})
    if not article: abort(404)
    return render_template("create_article.html", article=article, syndication_platforms=syndication.available_platforms(kind="article"))

@app.route("/api/save_article", methods=["POST"])
def api_save_article():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    title, action, article_id = request.form.get("title", "").strip(), request.form.get("action", "draft"), request.form.get("article_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    existing_article = posts_collection.find_one({"post_id": article_id})
    # Resolve the final id before uploads, so media is named after it.
    original_id = article_id
    if not article_id:
        article_id = ("article_" if action == "publish" else "draft_") + media.generate_post_id()
    elif action == "publish" and article_id.startswith("draft_"):
        # Promote the stored draft's URL from draft_* to article_* when published.
        article_id = "article_" + media.generate_post_id()
    taken: set = set()
    stem = media.media_stem(article_id)
    skipped = []
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename:
        if media.allowed_file(cover_file.filename):
            cover_image_url = media.upload_to_server(cover_file, stem, taken)
        else:
            skipped.append(cover_file.filename)
            cover_image_url = existing_article.get("cover_image") if existing_article else None
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
        "timestamp": current_time if (action == "publish" and (not existing_article or existing_article.get("status") != "published")) else (existing_article.get("timestamp", current_time) if existing_article else current_time)
    }
    posts_collection.update_one({"post_id": original_id or article_id}, {"$set": update_data}, upsert=True)
    if action == "publish":
        runner.enqueue_syndication(article_id, content.canonical("article_detail", article_id=article_id), request.form.getlist("platforms"))
    return jsonify({"status": "success", "article_id": article_id, "skipped": skipped})

@app.route("/api/syndication/check", methods=["POST"])
def api_syndication_check():
    if not session.get("logged_in"): return jsonify({"ok": False, "detail": "Unauthorized"}), 401
    s = syndication.get(request.form.get("platform", "linkedin"))
    if not s: return jsonify({"ok": False, "detail": "Unknown platform"}), 404
    return jsonify(s.check())

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


@app.route("/delete/<post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("logged_in"): abort(401)
    doc = posts_collection.find_one({"post_id": post_id})
    posts_collection.delete_one({"post_id": post_id})
    if doc and doc.get("type") == "article":
        flash("Article removed.", "success")
        return redirect(url_for("articles_dashboard"))
    flash("Post removed.", "success")
    return redirect(url_for("index"))

@app.route("/api/analytics", methods=["POST"])
@csrf.exempt
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
    return render_template("analytics.html", data=data, analytics_store=ANALYTICS_STORE)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", 5000)))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
