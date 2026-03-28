import json
import os
import random
import string
from datetime import datetime, timezone

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "blog-secret-key-change-in-production")

BLOG_JSON = os.path.join(os.path.dirname(__file__), "blog.json")
MEDIA_FOLDER = os.path.join(os.path.dirname(__file__), "media")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "KittuBlog@2026!")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "ogg", "mov", "avi", "mkv", "wmv", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"}
ALLOWED_MIMETYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/x-ms-wmv",
    "application/pdf",
    "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
}


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_posts():
    """Return the list of posts from blog.json."""
    if not os.path.exists(BLOG_JSON):
        return []
    with open(BLOG_JSON, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_posts(posts):
    """Persist the list of posts to blog.json."""
    with open(BLOG_JSON, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)


def generate_post_id(length=8):
    """Return a random alphanumeric post ID that is not already in use."""
    posts = load_posts()
    existing_ids = {p["post_id"] for p in posts}
    while True:
        new_id = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        if new_id not in existing_ids:
            return new_id


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def secure_name(filename):
    """Return a safe version of the filename (no spaces or traversal characters)."""
    filename = os.path.basename(filename)
    keep = set(string.ascii_letters + string.digits + "._-")
    safe = "".join(c if c in keep else "_" for c in filename)
    return safe or "file"


# ---------------------------------------------------------------------------
# Routes — public
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    posts = load_posts()
    # Show newest first
    posts = sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)
    return render_template("index.html", posts=posts)


@app.route("/feed")
def feed():
    return redirect(url_for("index"))


@app.route("/post")
@app.route("/post/")
def post_base():
    return redirect(url_for("index"))


@app.route("/post/<post_id>")
def post_detail(post_id):
    posts = load_posts()
    post = next((p for p in posts if p["post_id"] == post_id), None)
    if post is None:
        abort(404)
        
    # Analytics: Increment view count
    post["views"] = post.get("views", 0) + 1
    save_posts(posts)
    
    return render_template("post.html", post=post)


@app.route("/like/<post_id>", methods=["POST"])
def like_post(post_id):
    posts = load_posts()
    post = next((p for p in posts if p["post_id"] == post_id), None)
    if post:
        post["likes"] = post.get("likes", 0) + 1
        save_posts(posts)
        return {"status": "success", "likes": post["likes"]}
    return {"status": "error", "message": "Post not found"}, 404


@app.route("/media/<path:filename>")
def serve_media(filename):
    # Prevent path traversal: only allow plain filenames (no subdirectories)
    if os.sep in filename or (os.altsep and os.altsep in filename) or ".." in filename:
        abort(400)
    return send_from_directory(MEDIA_FOLDER, filename)


# ---------------------------------------------------------------------------
# Routes — auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Routes — Creation and Deletion (protected)
# ---------------------------------------------------------------------------

@app.route("/create_post", methods=["POST"])
def create_post():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    content = request.form.get("content", "").strip()
    media_files = request.files.getlist("media")

    if not content:
        flash("Content is required.", "error")
        return redirect(url_for("index"))

    # Save uploaded media files
    media_paths = []
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    for f in media_files:
        if f and f.filename and allowed_file(f.filename):
            if f.content_type and f.content_type.split(";")[0].strip() not in ALLOWED_MIMETYPES:
                continue
            safe_filename = secure_name(f.filename)
            unique = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            saved_name = f"{unique}_{safe_filename}"
            f.save(os.path.join(MEDIA_FOLDER, saved_name))
            media_paths.append(saved_name)

    # Build blocks schema
    blocks = [{"type": "text", "content": content}]
    if media_paths:
        blocks.append({"type": "media", "media_paths": media_paths})

    new_post = {
        "post_id": generate_post_id(),
        "type": "post",
        "title": None,
        "blocks": blocks,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
        "media_paths": media_paths,
    }

    posts = load_posts()
    posts.append(new_post)
    save_posts(posts)
    flash("Post published successfully!", "success")
    return redirect(url_for("index"))


@app.route("/create_article", methods=["GET", "POST"])
def create_article():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Article title is required.", "error")
            return redirect(url_for("create_article"))
            
        blocks_meta_str = request.form.get("blocks_meta", "[]")
        try:
            blocks_meta = json.loads(blocks_meta_str)
        except json.JSONDecodeError:
            blocks_meta = []

        final_blocks = []
        os.makedirs(MEDIA_FOLDER, exist_ok=True)
        
        fallback_text_parts = []
        fallback_media_paths = []

        for block in blocks_meta:
            if block.get("type") == "text":
                content = block.get("content", "").strip()
                if content:
                    final_blocks.append({"type": "text", "content": content})
                    fallback_text_parts.append(content)
            elif block.get("type") == "media":
                file_key = f"file_{block.get('fileIndex')}"
                f = request.files.get(file_key)
                if f and f.filename and allowed_file(f.filename):
                    if f.content_type and f.content_type.split(";")[0].strip() not in ALLOWED_MIMETYPES:
                        continue
                    safe_filename = secure_name(f.filename)
                    unique = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
                    saved_name = f"{unique}_{safe_filename}"
                    f.save(os.path.join(MEDIA_FOLDER, saved_name))
                    final_blocks.append({"type": "media", "media_paths": [saved_name]})
                    fallback_media_paths.append(saved_name)

        if not final_blocks:
            flash("Article must contain at least some content.", "error")
            return redirect(url_for("create_article"))

        new_post = {
            "post_id": generate_post_id(),
            "type": "article",
            "title": title,
            "blocks": final_blocks,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "content": "\n\n".join(fallback_text_parts),
            "media_paths": fallback_media_paths,
        }

        posts = load_posts()
        posts.append(new_post)
        save_posts(posts)
        flash("Article published successfully!", "success")
        return redirect(url_for("index"))

    return render_template("create_article.html")


@app.route("/delete/<post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    posts = load_posts()
    posts = [p for p in posts if p["post_id"] != post_id]
    save_posts(posts)
    flash("Post deleted.", "success")
    referrer = request.referrer
    if referrer and '/post/' in referrer:
        return redirect(url_for("index"))
    return redirect(referrer or url_for("index"))


if __name__ == "__main__":
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
