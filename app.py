import os
import json
import hashlib
import queue
import random
import string
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from src import syndication

from markupsafe import Markup, escape
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
    send_from_directory,
)
from dotenv import load_dotenv
from pymongo import MongoClient
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect

# Load environment variables from ".env" (git-ignored).
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-insecure-secret-key")
csrf = CSRFProtect(app)

# --- Database Setup ---
# Use the configured MongoDB/Cosmos URI when present; otherwise fall back to an
# in-process mongomock database so the app runs locally with no daemon.
MONGO_URI = os.environ.get("MONGO_URI")
# Either pymongo or the in-memory mongomock may fill this in below; they are
# separate types, so declare it explicitly rather than letting mypy infer one.
client: Any
if MONGO_URI:
    client = MongoClient(MONGO_URI)
else:
    import mongomock

    print("[startup] No MONGO_URI set — using in-memory mongomock database.")
    client = mongomock.MongoClient()
db = client.get_database("blog_db")
posts_collection = db.posts
comments_collection = db.comments

# --- Cloud Storage Setup (optional) ---
# Azure Blob Storage is used when configured; otherwise uploads are saved to the
# local media/ folder and served by the serve_media route below.
AZURE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.environ.get("AZURE_CONTAINER_NAME")
AZURE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")

container_client = None
if AZURE_CONNECTION_STRING and AZURE_CONTAINER_NAME:
    from azure.storage.blob import BlobServiceClient

    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
else:
    print("[startup] Azure Storage not configured — saving uploads to local media/ folder.")

# --- Configuration & Helpers ---
ADMIN_USERNAME = os.environ.get("BLOG_ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("BLOG_ADMIN_PASSWORD")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "ogg", "mov", "avi", "mkv", "wmv", "mp3", "wav", "m4a", "aac", "flac", "oga", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

MEDIA_FOLDER = os.path.join(os.path.dirname(__file__), "media")
os.makedirs(MEDIA_FOLDER, exist_ok=True)

UPLOAD_TOKEN = os.environ.get("UPLOAD_TOKEN", "").strip()


def upload_authorized() -> bool:
    """Authorise an upload: a logged-in admin, or the shared upload token.

    The token path exists so a script can POST to /upload_media without a
    browser session. Leave UPLOAD_TOKEN unset to disable it entirely.
    """
    if session.get("logged_in"):
        return True
    token = UPLOAD_TOKEN
    return bool(token) and request.headers.get("X-Upload-Token", "") == token


def media_stem(post_id: str) -> str:
    """Filename stem for a post's media: media_<hash of the post id>.

    Hashing keeps the name stable per post and independent of the id's own
    characters or length, while staying unique across posts.
    """
    return "media_" + hashlib.sha1(str(post_id).encode("utf-8")).hexdigest()[:16]


def _ext_of(filename: str) -> str:
    return os.path.splitext(secure_filename(filename or ""))[1].lower()


def _unique_name(stem: str, ext: str, taken: set, check_disk: bool = True) -> str:
    """`stem+ext`, or `stem_1+ext`, `stem_2+ext`... when that name is taken.

    Checks this request's uploads via `taken` and (for local storage) what is
    already on disk, so adding a second image to an existing post cannot
    silently overwrite the first.
    """
    n = 0
    while True:
        name = (stem if n == 0 else "%s_%d" % (stem, n)) + ext
        if name not in taken and not (check_disk and os.path.exists(os.path.join(MEDIA_FOLDER, name))):
            taken.add(name)
            return name
        n += 1


def upload_to_local(file, stem, taken):
    saved_name = _unique_name(stem, _ext_of(file.filename), taken)
    file.save(os.path.join(MEDIA_FOLDER, saved_name))
    return f"/media/{saved_name}"


def upload_to_azure(file, stem, taken):
    # Narrow the module-global before use: it is only set when Azure is
    # configured, so type checkers (rightly) see None as a possibility here.
    if container_client is None:
        raise RuntimeError("Azure Storage is not configured.")
    blob_name = _unique_name(stem, _ext_of(file.filename), taken, check_disk=False)
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(file.read(), overwrite=True)
    return f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_name}"


def upload_to_server(file, stem, taken):
    if globals().get("container_client"):
        return upload_to_azure(file, stem, taken)
    return upload_to_local(file, stem, taken)

def generate_post_id(length=8):
    while True:
        new_id = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        if not posts_collection.find_one({"post_id": new_id}):
            return new_id

def normalize_media_path(path):
    """Return a browser-usable URL for a stored media reference.

    Remote (http) URLs are returned untouched; bare filenames or paths are
    served from the local media/ folder via the serve_media route.
    """
    if not path:
        return path
    if path.startswith("http://") or path.startswith("https://"):
        return path
    filename = path.replace("/media/", "").lstrip("/")
    return f"/media/{filename}"

_FENCE_RE = re.compile(r"```([\w+-]*)\n(.*?)```", re.S)
_URL_RE = re.compile(r"https?://[^\s<]+")


def _embed_html(url):
    """Return an iframe embed for known media providers, else None."""
    yt = re.match(r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([\w-]{6,})", url)
    if yt:
        return '<iframe class="w-full aspect-video rounded-xl border border-slate-200 dark:border-slate-700 my-4" src="https://www.youtube.com/embed/%s" allowfullscreen loading="lazy"></iframe>' % yt.group(1)
    vm = re.match(r"https?://(?:www\.)?vimeo\.com/(\d+)", url)
    if vm:
        return '<iframe class="w-full aspect-video rounded-xl border border-slate-200 dark:border-slate-700 my-4" src="https://player.vimeo.com/video/%s" allowfullscreen loading="lazy"></iframe>' % vm.group(1)
    sp = re.match(r"https?://open\.spotify\.com/(track|album|playlist|episode|show|artist)/([\w]+)", url)
    if sp:
        return '<iframe class="w-full rounded-xl border border-slate-200 dark:border-slate-700 my-4" height="152" src="https://open.spotify.com/embed/%s/%s" loading="lazy"></iframe>' % (sp.group(1), sp.group(2))
    sc = re.match(r"https?://(?:www\.)?soundcloud\.com/[\w-]+/[\w-]+", url)
    if sc:
        return '<iframe class="w-full rounded-xl border border-slate-200 dark:border-slate-700 my-4" height="166" scrolling="no" src="https://w.soundcloud.com/player/?url=%s" loading="lazy"></iframe>' % urllib.parse.quote(url, safe="")


@app.template_filter("rich_text")
def rich_text(text):
    """Render post/article text: fenced code blocks, provider embeds, autolinks."""
    if not text:
        return Markup("")
    escaped = str(escape(text))
    blocks = []

    def _fence(m):
        lang, code = m.group(1), m.group(2)
        cls = (' class="language-%s"' % lang) if lang else ""
        blocks.append('<pre class="bg-slate-900 text-slate-100 rounded-xl p-4 overflow-x-auto my-4 text-sm"><code%s>%s</code></pre>' % (cls, code))
        return "\x00%d\x00" % (len(blocks) - 1)

    escaped = _FENCE_RE.sub(_fence, escaped)

    def _url(m):
        url = m.group(0)
        return _embed_html(url) or '<a href="%s" target="_blank" rel="noopener" class="text-brand-600 dark:text-brand-400 hover:underline break-all">%s</a>' % (url, url)

    escaped = _URL_RE.sub(_url, escaped)
    escaped = re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], escaped)
    return Markup(escaped)


def seed_database_if_empty():
    """Load starter content from blog.json into an empty collection.

    Useful for the mongomock fallback, which starts empty on every launch.
    """
    if posts_collection.count_documents({}) > 0:
        return
    seed_file = os.path.join(os.path.dirname(__file__), "blog.json")
    if not os.path.exists(seed_file):
        return
    with open(seed_file, encoding="utf-8") as fh:
        data = json.load(fh)
    docs = []
    for status, items in (("published", data.get("published", [])), ("draft", data.get("drafts", []))):
        for item in items:
            item.setdefault("status", status)
            item.setdefault("likes", 0)
            item.setdefault("views", 0)
            if item.get("cover_image"):
                item["cover_image"] = normalize_media_path(item["cover_image"])
            for block in item.get("blocks", []):
                if block.get("type") == "media" and block.get("media_paths"):
                    block["media_paths"] = [normalize_media_path(p) for p in block["media_paths"]]
            docs.append(item)
    if docs:
        posts_collection.insert_many(docs)
        print(f"[startup] Seeded {len(docs)} document(s) from blog.json.")

seed_database_if_empty()

# ---------------------------------------------------------------------------
# Syndication (POSSE)
# ---------------------------------------------------------------------------
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


def canonical(endpoint, **values):
    """Absolute URL of a blog page, honouring SITE_URL when set."""
    if SITE_URL:
        return SITE_URL + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def syndication_link_reserve():
    """Characters the appended canonical link will occupy in a syndicated post.

    The editor's live counter reserves this so a post that fits only without its
    link is not reported as fitting. Ids are 8 characters (generate_post_id).
    """
    if not SITE_URL or not syndication.is_public_url(SITE_URL):
        return 0
    return len("\n\n" + SITE_URL + "/post/" + "x" * 8)


@app.context_processor
def _template_urls():
    """Expose canonical()/SITE_URL so templates can emit <link rel=canonical>
    and Open Graph tags - importers (Medium) and link previews need absolute
    URLs, which url_for() alone cannot build behind a tunnel/proxy."""
    return {"canonical": canonical, "site_url": SITE_URL,
            "link_reserve": syndication_link_reserve(),
            # A text card is rendered locally and uploaded by the adapter, so
            # Pillow is the only requirement - no public URL is involved.
            "text_card_available": bool(syndication.textcard.available())}


def _now_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def notify_telegram(doc, results):
    """Send a summary of a completed syndication run to Telegram.

    Enabled by TELEGRAM_BOT_TOKEN (from @BotFather) + TELEGRAM_CHAT_ID. Both are
    optional: with either missing this is a silent no-op, so syndication never
    depends on Telegram being configured.
    """
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    title = (doc.get("title") or doc.get("content") or "New post").strip()[:120]
    lines = ["Syndicated: " + title]
    for r in results:
        label = r.get("label") or r.get("platform")
        if r.get("status") == "posted" and r.get("url"):
            lines.append("- %s: %s" % (label, r["url"]))
        else:
            lines.append("- %s: FAILED %s" % (label, (r.get("error") or "unknown")[:120]))
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "\n".join(lines),
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_BOT_TOKEN,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except Exception as e:
        # Never let a notification failure break syndication.
        print("[telegram] notify failed:", e)


def run_syndication(doc_id, url, platforms):
    """Publish a doc to each platform, recording the resulting URL on the doc."""
    doc = posts_collection.find_one({"post_id": doc_id})
    if not doc:
        return []
    media = syndication.media_for(doc)
    already = {s.get("platform") for s in doc.get("syndications", []) if s.get("status") == "posted"}
    results = []
    for pid in platforms:
        if pid in already:
            continue
        # Composed per platform. A single shared string had to satisfy the
        # smallest limit in the batch, so Bluesky's 300 characters truncated a
        # post that Facebook would happily have taken in full.
        text = syndication.compose_text(doc, url, [pid])
        # Instagram and Pinterest cannot publish text at all. Render a text card
        # for them instead of failing. YouTube is excluded on purpose: it needs
        # a real video, which cannot be derived from text.
        platform_media = list(media)
        if pid in syndication.TEXT_CARD_PLATFORMS and not platform_media:
            # Rendered locally; the adapter uploads it and publishes by media_id,
            # so this needs no public URL and works on a local machine.
            try:
                platform_media = [syndication.textcard.write(
                    text, MEDIA_FOLDER, doc.get("post_id") or doc_id)]
            except Exception as e:
                print("[textcard] could not render for %s: %s" % (pid, e))
        try:
            outcome = syndication.publish_detailed_to(pid, text, url, platform_media, doc)
            rec = {"platform": pid, "label": syndication.label_for(pid), "url": outcome.get("url"),
                   "remote_id": outcome.get("remote_id"), "status": "posted", "posted_at": _now_str(), "error": None}
        except Exception as e:
            rec = {"platform": pid, "label": syndication.label_for(pid), "url": None,
                   "remote_id": None, "status": "failed", "posted_at": _now_str(), "error": str(e)[:300]}
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": rec}})
        results.append(rec)
    if results:
        notify_telegram(doc, results)
    return results


def enqueue_syndication(doc_id, url, platforms):
    """Mark platforms queued and hand the work to the background worker."""
    platforms = [p for p in (platforms or []) if p]
    if not platforms:
        return
    for pid in platforms:
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": {
            "platform": pid, "label": syndication.label_for(pid), "url": None, "status": "queued", "posted_at": _now_str(), "error": None}}})
    _syn_queue.put((doc_id, url, platforms))


def _syndication_worker():
    while True:
        doc_id, url, platforms = _syn_queue.get()
        try:
            run_syndication(doc_id, url, platforms)
        except Exception as e:
            print("[syndication] error:", e)
        finally:
            _syn_queue.task_done()


_syn_queue: "queue.Queue[tuple[str, str, list[str]]]" = queue.Queue()
threading.Thread(target=_syndication_worker, daemon=True).start()

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
    if not upload_authorized():
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    f = request.files.get("file") or request.files.get("media")
    if not f or not f.filename:
        return jsonify({"status": "error", "message": "No file provided."}), 400
    if not allowed_file(f.filename):
        return jsonify({"status": "error", "message": "Unsupported file type."}), 400

    post_id = request.form.get("post_id", "").strip() or generate_post_id()
    url = upload_to_server(f, media_stem(post_id), set())
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

    posts_collection.update_one({"post_id": post_id}, {"$inc": {"views": 1}})
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
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    })
    flash("Comment posted.", "success")
    return redirect(target)

@app.route("/article/<article_id>")
def article_detail(article_id):
    article = posts_collection.find_one({"post_id": article_id, "type": "article"})
    if not article: abort(404)
    if article.get("status") == "draft" and not session.get("logged_in"): abort(404)
    posts_collection.update_one({"post_id": article_id}, {"$inc": {"views": 1}})
    return render_template("article.html", post=article)

@app.route("/like/<post_id>", methods=["POST"])
def like_post(post_id):
    result = posts_collection.find_one_and_update({"post_id": post_id}, {"$inc": {"likes": 1}}, return_document=True)
    if result: return jsonify({"status": "success", "likes": result.get("likes", 0)})
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
    content = request.form.get("content", "").strip()
    media_files = request.files.getlist("media")
    if not content:
        flash("Content is required.", "error")
        return redirect(url_for("index"))
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    # The id must exist before uploads, so media can be named after it.
    post_id = generate_post_id()
    taken: set = set()
    stem = media_stem(post_id)
    media_urls = [upload_to_server(f, stem, taken) for f in media_files if f and allowed_file(f.filename)]
    blocks: list[dict] = [{"type": "text", "content": content}]
    if media_urls:
        blocks.append({"type": "media", "media_paths": media_urls})
    new_post = {
        "post_id": post_id, "type": "post",
        "blocks": blocks, "tags": tags,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "published", "likes": 0, "views": 0
    }
    posts_collection.insert_one(new_post)
    enqueue_syndication(post_id, canonical("post_detail", post_id=post_id),
                        request.form.getlist("platforms"))
    flash("Post published to cloud!", "success")
    return redirect(url_for("index"))

def post_text_and_media(post):
    if not post:
        return "", []
    blocks = post.get("blocks", [])
    text = "\n\n".join(b.get("content", "").strip() for b in blocks if b.get("type") == "text")
    media = [p for b in blocks if b.get("type") == "media" for p in b.get("media_paths", [])]
    return text, media

@app.route("/edit_post/<post_id>", methods=["GET"])
def edit_post(post_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    post = posts_collection.find_one({"post_id": post_id})
    if not post: abort(404)
    text, media = post_text_and_media(post)
    published_articles = list(posts_collection.find({"type": "article", "status": "published"}).sort("timestamp", -1))
    published_posts = list(posts_collection.find({"type": "post", "status": "published"}).sort("timestamp", -1).limit(20))
    return render_template("post_editor.html", post=post, content=text, media_paths=media, articles=published_articles, attach_posts=published_posts, syndication_platforms=syndication.available_platforms(kind="post"))

@app.route("/api/save_post", methods=["POST"])
def api_save_post():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    content = request.form.get("content", "").strip()
    action = request.form.get("action", "draft")
    post_id = request.form.get("post_id", "").strip()
    tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
    if action == "publish" and not content:
        return jsonify({"status": "error", "message": "Content is required to publish."}), 400
    existing = posts_collection.find_one({"post_id": post_id}) if post_id else None
    try:
        keep_media = json.loads(request.form.get("keep_media", "[]"))
    except (TypeError, ValueError):
        keep_media = []
    # Resolve the id before uploads, so media is named after it.
    if not post_id:
        post_id = generate_post_id()
    taken: set = set()
    stem = media_stem(post_id)
    media_paths = list(keep_media)
    skipped = []
    try:
        new_files = int(request.form.get("new_files", "0") or 0)
    except (TypeError, ValueError):
        new_files = 0
    for i in range(new_files):
        f = request.files.get(f"file_{i}")
        if f and f.filename:
            if allowed_file(f.filename): media_paths.append(upload_to_server(f, stem, taken))
            else: skipped.append(f.filename)
    blocks: list[dict] = [{"type": "text", "content": content}]
    if media_paths:
        blocks.append({"type": "media", "media_paths": media_paths})
    status = "published" if action == "publish" else "draft"
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    update_data = {
        "post_id": post_id, "type": "post", "blocks": blocks, "status": status, "tags": tags,
        "timestamp": current_time if status == "published" else (existing.get("timestamp", current_time) if existing else current_time),
        "likes": existing.get("likes", 0) if existing else 0,
        "views": existing.get("views", 0) if existing else 0,
    }
    posts_collection.update_one({"post_id": post_id}, {"$set": update_data}, upsert=True)
    if status == "published":
        enqueue_syndication(post_id, canonical("post_detail", post_id=post_id), request.form.getlist("platforms"))
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
        article_id = ("article_" if action == "publish" else "draft_") + generate_post_id()
    elif action == "publish" and article_id.startswith("draft_"):
        # Promote the stored draft's URL from draft_* to article_* when published.
        article_id = "article_" + generate_post_id()
    taken: set = set()
    stem = media_stem(article_id)
    skipped = []
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename:
        if allowed_file(cover_file.filename):
            cover_image_url = upload_to_server(cover_file, stem, taken)
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
                if f and allowed_file(f.filename): final_blocks.append({"type": "media", "media_paths": [upload_to_server(f, stem, taken)]})
                elif f and f.filename: skipped.append(f.filename)
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    update_data = {
        "post_id": article_id, "type": "article", "title": title, "cover_image": cover_image_url, "blocks": final_blocks, "tags": tags,
        "status": "published" if action == "publish" else "draft",
        "timestamp": current_time if (action == "publish" and (not existing_article or existing_article.get("status") != "published")) else (existing_article.get("timestamp", current_time) if existing_article else current_time)
    }
    posts_collection.update_one({"post_id": original_id or article_id}, {"$set": update_data}, upsert=True)
    if action == "publish":
        enqueue_syndication(article_id, canonical("article_detail", article_id=article_id), request.form.getlist("platforms"))
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
        url = canonical("article_detail", article_id=post_id)
    else:
        url = canonical("post_detail", post_id=post_id)
    enqueue_syndication(post_id, url, platforms)
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
        url = canonical("article_detail", article_id=post_id)
    else:
        url = canonical("post_detail", post_id=post_id)

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", 5000)))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")