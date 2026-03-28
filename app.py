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
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "ogg"}
ALLOWED_MIMETYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp",
    "video/mp4", "video/webm", "video/ogg",
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


@app.route("/post/<post_id>")
def post_detail(post_id):
    posts = load_posts()
    post = next((p for p in posts if p["post_id"] == post_id), None)
    if post is None:
        abort(404)
    return render_template("post.html", post=post)


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
            return redirect(url_for("admin"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Routes — admin (protected)
# ---------------------------------------------------------------------------

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        post_type = request.form.get("type", "").strip()
        content = request.form.get("content", "").strip()
        media_files = request.files.getlist("media")

        if not content:
            flash("Content is required.", "error")
            return redirect(url_for("admin"))

        # Save uploaded media files
        media_paths = []
        os.makedirs(MEDIA_FOLDER, exist_ok=True)
        for f in media_files:
            if f and f.filename and allowed_file(f.filename):
                # Also check the MIME type reported by the browser
                if f.content_type and f.content_type.split(";")[0].strip() not in ALLOWED_MIMETYPES:
                    continue
                safe_filename = secure_name(f.filename)
                # Prepend a unique token to avoid name collisions
                unique = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
                saved_name = f"{unique}_{safe_filename}"
                f.save(os.path.join(MEDIA_FOLDER, saved_name))
                media_paths.append(saved_name)

        new_post = {
            "post_id": generate_post_id(),
            "type": post_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "media_paths": media_paths,
        }

        posts = load_posts()
        posts.append(new_post)
        save_posts(posts)
        flash("Post published successfully!", "success")
        return redirect(url_for("admin"))

    posts = load_posts()
    posts = sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)
    return render_template("admin.html", posts=posts)


@app.route("/admin/delete/<post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    posts = load_posts()
    posts = [p for p in posts if p["post_id"] != post_id]
    save_posts(posts)
    flash("Post deleted.", "success")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
