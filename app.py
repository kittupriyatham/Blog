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
            data = json.load(f)
            if isinstance(data, dict):
                # Reconstruct flat list for routing logic natively
                return data.get("published", []) + data.get("drafts", [])
            return data
        except json.JSONDecodeError:
            return []


def save_posts(posts):
    """Persist the list of posts physically separated into blog.json."""
    # Separate strictly for on-disk readability
    published = [p for p in posts if p.get("status") != "draft"]
    drafts = [p for p in posts if p.get("status") == "draft"]
    
    with open(BLOG_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "published": published,
            "drafts": drafts
        }, f, indent=2, ensure_ascii=False)


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

import re

@app.route("/")
def index():
    posts = load_posts()
    
    # Map out articles for fast lookup
    all_articles = {p["post_id"]: p for p in posts if p.get("type") == "article"}
    
    # Isolate standard posts for organic timeline
    feed_posts = [p for p in posts if p.get("type", "post") != "article"]
    
    # Detect internal article links
    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    for p in feed_posts:
        content = p.get("content", "")
        match = pattern.search(content)
        if match:
            article_id = match.group(1)
            if article_id in all_articles:
                p["embedded_article"] = all_articles[article_id]
                
    # Show newest first
    feed_posts = sorted(feed_posts, key=lambda p: p.get("timestamp", ""), reverse=True)
    return render_template("index.html", posts=feed_posts)


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

@app.route("/article/<article_id>")
def article_detail(article_id):
    posts = load_posts()
    article = next((p for p in posts if p["post_id"] == article_id and p.get("type") == "article"), None)
    if article is None:
        abort(404)
        
    # Enforce Draft Privacy
    if article.get("status") == "draft" and not session.get("logged_in"):
        abort(404)
        
    # Analytics: Increment view count
    article["views"] = article.get("views", 0) + 1
    save_posts(posts)
    
    return render_template("article.html", post=article)


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


@app.route("/articles")
def articles_dashboard():
    posts = load_posts()
    # Filter only articles and sort by newest
    all_articles = [p for p in posts if p.get("type") == "article"]
    all_articles = sorted(all_articles, key=lambda p: p.get("timestamp", ""), reverse=True)
    
    # Bucket into published vs drafts (default to published for legacy)
    published = [p for p in all_articles if p.get("status", "published") == "published"]
    drafts = [p for p in all_articles if p.get("status", "published") == "draft"]
    
    return render_template("articles.html", published=published, drafts=drafts)


@app.route("/posts")
def posts_dashboard():
    posts = load_posts()
    all_articles = {p["post_id"]: p for p in posts if p.get("type", "") == "article"}
    posts_list = [p for p in posts if p.get("type", "post") == "post"]
    
    # Detect internal article links
    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    for p in posts_list:
        content = p.get("content", "")
        match = pattern.search(content)
        if match:
            article_id = match.group(1)
            if article_id in all_articles:
                p["embedded_article"] = all_articles[article_id]
                
    posts_list = sorted(posts_list, key=lambda p: p.get("timestamp", ""), reverse=True)
    return render_template("posts.html", posts_list=posts_list)


@app.route("/create_article", methods=["GET"])
def create_article():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("create_article.html", article=None)


@app.route("/edit_article/<article_id>", methods=["GET"])
def edit_article(article_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    posts = load_posts()
    article = next((p for p in posts if p.get("post_id") == article_id and p.get("type") == "article"), None)
    if not article:
        abort(404)
    return render_template("create_article.html", article=article)


@app.route("/api/save_article", methods=["POST"])
def api_save_article():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    title = request.form.get("title", "").strip()
    action = request.form.get("action", "draft")  # expected "draft" or "publish"
    article_id = request.form.get("article_id", "").strip()
    
    if not title and action == "publish":
        return jsonify({"status": "error", "message": "Article title is required to publish."}), 400

    posts = load_posts()
    existing_article = next((p for p in posts if p.get("post_id") == article_id), None)
    
    cover_image_file = request.files.get("cover_image")
    cover_image_name = existing_article.get("cover_image") if existing_article else None

    # Enforce Cover Image rules (Drafts accept None)
    if cover_image_file and cover_image_file.filename and allowed_file(cover_image_file.filename):
        os.makedirs(MEDIA_FOLDER, exist_ok=True)
        safe_filename = secure_name(cover_image_file.filename)
        unique = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        cover_image_name = f"cover_{unique}_{safe_filename}"
        cover_image_file.save(os.path.join(MEDIA_FOLDER, cover_image_name))
    elif action == "publish" and not cover_image_name:
        return jsonify({"status": "error", "message": "A cover image is required to publish."}), 400

    blocks_meta_str = request.form.get("blocks_meta", "[]")
    try:
        blocks_meta = json.loads(blocks_meta_str)
    except json.JSONDecodeError:
        blocks_meta = []

    final_blocks = []
    fallback_text_parts = []
    fallback_media_paths = []
    os.makedirs(MEDIA_FOLDER, exist_ok=True)

    for block in blocks_meta:
        if block.get("type") == "text":
            content = block.get("content", "").strip()
            if content:
                final_blocks.append({"type": "text", "content": content})
                fallback_text_parts.append(content)
        elif block.get("type") == "media":
            # Preserve existing loaded media arrays if no new file is uploaded
            if block.get("saved_path"):
                saved_path = block.get("saved_path")
                final_blocks.append({"type": "media", "media_paths": [saved_path]})
                fallback_media_paths.append(saved_path)
            else:
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

    if not final_blocks and action == "publish":
        return jsonify({"status": "error", "message": "Article must contain content to publish."}), 400

    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    if existing_article:
        existing_article["title"] = title
        existing_article["cover_image"] = cover_image_name
        existing_article["blocks"] = final_blocks
        existing_article["content"] = "\n\n".join(fallback_text_parts)
        existing_article["media_paths"] = fallback_media_paths
        
        # Handle ID restructuring when transitioning out of a draft state or upgrading a legacy article
        if action == "publish":
            old_id = existing_article["post_id"]
            new_id = old_id
            
            if old_id.startswith("draft_"):
                new_id = old_id.replace("draft_", "article_", 1)
            elif not old_id.startswith("article_"):
                new_id = "article_" + old_id
                
            if new_id != old_id:
                existing_article["post_id"] = new_id
                # Link Auto-Healer: Retroactively update all embedded feed posts referring to the old ID
                for p in posts:
                    if p.get("type", "post") == "post" and old_id in p.get("content", ""):
                        p["content"] = p["content"].replace(old_id, new_id)
        
        # User defined: "when clicked publish use published time, not first draft time"
        if action == "publish" and existing_article.get("status") != "published":
            existing_article["timestamp"] = current_time
            
        existing_article["status"] = "published" if action == "publish" else action
        saved_post = existing_article
    else:
        raw_new_id = article_id if article_id else ("draft_" + generate_post_id())
        
        if action == "publish":
            if raw_new_id.startswith("draft_"):
                raw_new_id = raw_new_id.replace("draft_", "article_", 1)
            elif not raw_new_id.startswith("article_"):
                raw_new_id = "article_" + raw_new_id
                
        new_post = {
            "post_id": raw_new_id,
            "type": "article",
            "title": title,
            "cover_image": cover_image_name,
            "blocks": final_blocks,
            "timestamp": current_time,
            "content": "\n\n".join(fallback_text_parts),
            "media_paths": fallback_media_paths,
            "status": "published" if action == "publish" else action
        }
        posts.append(new_post)
        saved_post = new_post

    save_posts(posts)
    return jsonify({
        "status": "success",
        "action": action,
        "article_id": saved_post["post_id"],
        "message": "Article published successfully!" if action == "publish" else "Draft saved."
    })



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
