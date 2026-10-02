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
from src.config import (ADMIN_PASSWORD, ADMIN_USERNAME, ANALYTICS_STORE, MEDIA_FOLDER,
                        SECRET_KEY, YOUTUBE_CATEGORY, YOUTUBE_VISIBILITY)
from src.db import Comment, Post, connect_db, ensure_schema
from src.syndication import runner, socialapi_metrics

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
    platforms = request.form.getlist("platforms")
    youtube_meta = _parse_youtube_meta(request.form.get("youtube_meta"))
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
    new_post = {
        "post_id": post_id, "type": "post",
        "blocks": blocks, "tags": tags,
        "timestamp": content.now_str(),
        "status": "published", "likes": 0, "views": 0
    }
    # Metadata collected in the composer's YouTube panel, stored as doc["youtube"]
    # so the hand-off page arrives prefilled (no re-entry).
    if youtube_meta:
        new_post["youtube"] = youtube_meta
    posts_collection.insert_one(new_post)
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
    text, media_paths = content.post_text_and_media(post)
    published_articles = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
    published_posts = list(posts_collection.find({"type": "post", "status": "published"}).sort("timestamp", -1).limit(20))
    return render_template("post_editor.html", post=post, content=text, media_paths=media_paths, articles=published_articles, attach_posts=published_posts,
                           syndication_platforms=syndication.available_platforms(kind="post"),
                           youtube_meta=(post.get("youtube") or {}))

@app.route("/api/save_post", methods=["POST"])
def api_save_post():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    # Named `body` (not `content`) so the src.content package stays reachable.
    body = request.form.get("content", "").strip()
    action = request.form.get("action", "draft")
    post_id = request.form.get("post_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    platforms = request.form.getlist("platforms")
    youtube_meta = _parse_youtube_meta(request.form.get("youtube_meta"))
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
    }
    # Metadata collected in the editor's YouTube panel -> doc["youtube"] (merged so
    # a dedicated upload's `video` key survives an edit).
    if youtube_meta:
        update_data["youtube"] = _merge_youtube_meta(existing, youtube_meta)
    posts_collection.update_one({"post_id": post_id}, {"$set": update_data}, upsert=True)
    response = {"status": "success", "post_id": post_id, "skipped": skipped}
    if status == "published":
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

# --- YouTube upload ---------------------------------------------------------
# The common YouTube categories as (id, name). "22" (People & Blogs) is the
# default from src.config.YOUTUBE_CATEGORY; so is the visibility, from
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
    return render_template("create_article.html", article=article,
                           syndication_platforms=syndication.available_platforms(kind="article"),
                           youtube_meta=(article.get("youtube") or {}))

@app.route("/api/save_article", methods=["POST"])
def api_save_article():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    title, action, article_id = request.form.get("title", "").strip(), request.form.get("action", "draft"), request.form.get("article_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    youtube_meta = _parse_youtube_meta(request.form.get("youtube_meta"))
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
        "timestamp": current_time if (action == "publish" and (not existing_article or existing_article.get("status") != "published")) else (existing_article.get("timestamp", current_time) if existing_article else current_time)
    }
    # Metadata collected in the article editor's YouTube panel -> doc["youtube"].
    if youtube_meta:
        update_data["youtube"] = _merge_youtube_meta(existing_article, youtube_meta)
    posts_collection.update_one({"post_id": original_id or article_id}, {"$set": update_data}, upsert=True)
    response = {"status": "success", "article_id": article_id, "skipped": skipped}
    if action == "publish":
        platforms = request.form.getlist("platforms")
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


@app.route("/api/syndication/preview", methods=["POST"])
@csrf.exempt
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
    # Named `body_text` (not `content`) so the src.content package stays reachable.
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

    Read-only against SocialAPI (see src/syndication/socialapi_metrics.py). It
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
        posts_collection.update_one({"post_id": doc.get("post_id")},
                                   {"$set": {"platform_metrics": metrics}})
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
