import os
import json
import random
import string
import urllib.parse
import re
from datetime import datetime, timezone

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
)
from dotenv import load_dotenv
from pymongo import MongoClient
from azure.storage.blob import BlobServiceClient
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# --- Cloud Infrastructure Setup ---
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database("blog_db")
posts_collection = db.posts

AZURE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.environ.get("AZURE_CONTAINER_NAME")
AZURE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")

blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

# --- Configuration & Helpers ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "ogg", "mov", "avi", "mkv", "wmv", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_azure(file):
    original_name = secure_filename(file.filename)
    unique_prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    blob_name = f"{unique_prefix}_{original_name}"
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(file.read(), overwrite=True)
    return f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_name}"

def generate_post_id(length=8):
    while True:
        new_id = "".join(random.choices(string.ascii_letters + string.digits, k=length))
        if not posts_collection.find_one({"post_id": new_id}):
            return new_id

# ---------------------------------------------------------------------------
# Routes — Public
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    query = {"$or": [{"status": "published"}, {"status": {"$exists": False}}]}
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
    
    all_articles = {p["post_id"]: p for p in all_docs if p.get("type") == "article"}
    feed_posts = [p for p in all_docs if p.get("type", "post") != "article"]
    
    pattern = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")
    for p in feed_posts:
        content = p.get("content", "")
        match = pattern.search(content)
        if match and match.group(1) in all_articles:
            p["embedded_article"] = all_articles[match.group(1)]
                
    return render_template("index.html", posts=feed_posts)

@app.route("/post/<post_id>")
def post_detail(post_id):
    post = posts_collection.find_one({"post_id": post_id})
    if not post: abort(404)
    
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
        linked_article = posts_collection.find_one({"post_id": match.group(1), "type": "article"})
        if linked_article: post["embedded_article"] = linked_article

    posts_collection.update_one({"post_id": post_id}, {"$inc": {"views": 1}})
    return render_template("post.html", post=post)

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

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/create_post", methods=["POST"])
def create_post():
    if not session.get("logged_in"): return redirect(url_for("login"))
    content = request.form.get("content", "").strip()
    media_files = request.files.getlist("media")
    if not content:
        flash("Content is required.", "error")
        return redirect(url_for("index"))
    media_urls = [upload_to_azure(f) for f in media_files if f and allowed_file(f.filename)]
    new_post = {
        "post_id": generate_post_id(), "type": "post",
        "blocks": [{"type": "text", "content": content}, {"type": "media", "media_paths": media_urls}],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "published", "likes": 0, "views": 0
    }
    posts_collection.insert_one(new_post)
    flash("Post published to cloud!", "success")
    return redirect(url_for("index"))

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
                
    return render_template("posts.html", posts_list=posts_list)

@app.route("/create_article", methods=["GET"])
def create_article():
    if not session.get("logged_in"): return redirect(url_for("login"))
    return render_template("create_article.html", article=None)

@app.route("/edit_article/<article_id>", methods=["GET"])
def edit_article(article_id):
    if not session.get("logged_in"): return redirect(url_for("login"))
    article = posts_collection.find_one({"post_id": article_id, "type": "article"})
    if not article: abort(404)
    return render_template("create_article.html", article=article)

@app.route("/api/save_article", methods=["POST"])
def api_save_article():
    if not session.get("logged_in"): return jsonify({"status": "error", "message": "Unauthorized"}), 401
    title, action, article_id = request.form.get("title", "").strip(), request.form.get("action", "draft"), request.form.get("article_id", "").strip()
    existing_article = posts_collection.find_one({"post_id": article_id})
    cover_file = request.files.get("cover_image")
    cover_image_url = upload_to_azure(cover_file) if cover_file and allowed_file(cover_file.filename) else (existing_article.get("cover_image") if existing_article else None)
    blocks_meta = json.loads(request.form.get("blocks_meta", "[]"))
    final_blocks = []
    for block in blocks_meta:
        if block.get("type") == "text": final_blocks.append(block)
        elif block.get("type") == "media":
            if block.get("saved_path"): final_blocks.append({"type": "media", "media_paths": [block.get("saved_path")]})
            else:
                f = request.files.get(f"file_{block.get('fileIndex')}")
                if f and allowed_file(f.filename): final_blocks.append({"type": "media", "media_paths": [upload_to_azure(f)]})
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if not article_id: article_id = ("article_" if action == "publish" else "draft_") + generate_post_id()
    update_data = {
        "post_id": article_id, "type": "article", "title": title, "cover_image": cover_image_url, "blocks": final_blocks,
        "status": "published" if action == "publish" else "draft",
        "timestamp": current_time if (action == "publish" and (not existing_article or existing_article.get("status") != "published")) else (existing_article.get("timestamp", current_time) if existing_article else current_time)
    }
    posts_collection.update_one({"post_id": article_id}, {"$set": update_data}, upsert=True)
    return jsonify({"status": "success", "article_id": article_id})

@app.route("/delete/<post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("logged_in"): abort(401)
    posts_collection.delete_one({"post_id": post_id})
    flash("Post removed.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")