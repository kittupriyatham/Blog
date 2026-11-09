"""REST API endpoints for Posts, Articles, Comments, Reactions, and Tags."""

import math
from flask import Blueprint, current_app, jsonify, request, session
from core.api.v1.auth import _mobile_request
from core.db import Comment, Post
from core import analytics, content, media
from core.api.v1.serializers import serialize_comment, serialize_post

api_v1 = Blueprint("api_v1", __name__)


def _posts_collection():
    return Post._get_collection()


def _comments_collection():
    return Comment._get_collection()


def _can_view_draft(post):
    if post.get("status") != "draft":
        return True
    return bool(session.get("logged_in")) and (
        not session.get("is_demo") or post.get("is_demo") is True
    )


@api_v1.route("/posts", methods=["GET"])
def get_posts():
    """Paginated list of posts and articles.

    Query parameters:
      - page: int (>= 1, default 1)
      - limit / per_page: int (1..50, default 10)
      - type: filter by type, e.g. 'post' or 'article' (optional)
      - tag: filter by tag (optional)
      - q: search query for title/content (optional)
    """
    col = _posts_collection()

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        limit = min(50, max(1, int(request.args.get("limit") or request.args.get("per_page") or 10)))
    except (TypeError, ValueError):
        limit = 10

    post_type = request.args.get("type", "").strip()
    tag = request.args.get("tag", "").strip()
    q = request.args.get("q", "").strip()

    # Query conditions
    query = {"$or": [{"status": "published"}, {"status": {"$exists": False}}]}

    # Real admins can inspect all posts; demo users can only inspect published
    # posts and drafts created by the demo account.
    if request.args.get("status") == "all":
        if session.get("logged_in") and not session.get("is_demo"):
            query = {}
        elif session.get("logged_in") and session.get("is_demo"):
            query = {
                "$or": [
                    {"status": "published"},
                    {"status": {"$exists": False}},
                    {"is_demo": True},
                ]
            }

    filters = [query]
    admin_all = (request.args.get("status") == "all" and session.get("logged_in")
                 and not session.get("is_demo"))
    if not admin_all and not (session.get("logged_in") and session.get("is_demo")):
        filters.append({"is_demo": {"$ne": True}})

    if post_type:
        filters.append({"type": post_type})

    if tag:
        filters.append({"tags": tag})

    if q:
        import re
        safe_q = re.escape(q)
        filters.append({
            "$or": [
                {"title": {"$regex": safe_q, "$options": "i"}},
                {"content": {"$regex": safe_q, "$options": "i"}},
                {"blocks.content": {"$regex": safe_q, "$options": "i"}},
            ]
        })

    mongo_filter = {"$and": filters} if len(filters) > 1 else query

    total = col.count_documents(mongo_filter)
    total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1

    skip = (page - 1) * limit
    cursor = col.find(mongo_filter).sort("timestamp", -1).skip(skip).limit(limit)
    raw_posts = list(cursor)

    posts = [serialize_post(p, resolve_embedded=True, posts_collection=col) for p in raw_posts]

    return jsonify({
        "status": "success",
        "posts": posts,
        "page": page,
        "per_page": limit,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    })


@api_v1.route("/posts", methods=["POST"])
def create_post():
    """Create a new post or article via mobile app or API.

    Requires an authenticated session (admin or demo).
    JSON payload:
      - title: string (required for published articles)
      - content: string (required)
      - type: 'post' | 'article' (default: 'post')
      - tags: list[str] or comma-separated string
      - status: 'published' | 'draft' (default: 'published')
    """
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    # Only sessions established by native login can use the mobile JSON path.
    # Browser requests must supply the usual Flask-WTF CSRF token.
    if not (session.get("mobile_authenticated") and _mobile_request() and request.is_json):
        current_app.extensions["csrf"].protect()

    data = request.get_json(silent=True) if request.is_json else request.form
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Request data must be an object."}), 400
    for field in ("content", "body", "title", "type", "status"):
        if field in data and not isinstance(data[field], str):
            return jsonify({"status": "error", "message": f"{field} must be a string."}), 400
    content_body = (data.get("content") or data.get("body") or "").strip()
    if not content_body:
        return jsonify({"status": "error", "message": "Content is required."}), 400

    title = (data.get("title") or "").strip()
    post_type = (data.get("type") or "post").strip().lower()
    if post_type not in ("post", "article"):
        post_type = "post"

    tags_raw = data.get("tags") or []
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    elif isinstance(tags_raw, list):
        tags = [str(t).strip() for t in tags_raw if str(t).strip()]
    else:
        tags = []

    post_status = (data.get("status") or "published").strip().lower()
    if post_status not in ("published", "draft"):
        post_status = "published"
    if post_type == "article" and post_status == "published" and not title:
        return jsonify({"status": "error", "message": "Article title is required to publish."}), 400

    col = _posts_collection()
    post_id = media.generate_post_id(posts_collection=col)
    now = content.now_str()

    blocks = [{"type": "text", "content": content_body}]

    is_demo = bool(session.get("is_demo"))
    author = "Demo Publisher" if is_demo else (session.get("username") or "Kittu Priyatham")

    new_post = {
        "post_id": post_id,
        "type": post_type,
        "title": title,
        "content": content_body,
        "blocks": blocks,
        "tags": tags,
        "timestamp": now,
        "status": post_status,
        "likes": 0,
        "views": 0,
        "shares": 0,
        "reactions": {"like": 0, "heart": 0, "fire": 0, "clap": 0, "insightful": 0},
        "is_demo": is_demo,
        "author": author,
    }

    res = col.insert_one(new_post)
    new_post["_id"] = res.inserted_id

    analytics.record_analytics({
        "event": "create_post",
        "post_id": post_id,
        "type": post_type,
        "is_demo": is_demo,
    })

    serialized = serialize_post(new_post, resolve_embedded=False)
    return jsonify({
        "status": "success",
        "message": "Post created successfully",
        "post": serialized,
    }), 201


@api_v1.route("/posts/<post_id>", methods=["GET"])
def get_post_detail(post_id):
    """Get single post or article by post_id."""
    col = _posts_collection()
    doc = col.find_one({"post_id": post_id})

    if not doc:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    if not _can_view_draft(doc):
        return jsonify({"status": "error", "message": "Post not found"}), 404

    track_view = request.args.get("track_view", "true").lower() in ("1", "true")
    if track_view and not session.get("logged_in"):
        col.update_one({"post_id": post_id}, {"$inc": {"views": 1}})
        analytics.record_analytics({
            "event": "view",
            "post_id": post_id,
            "type": doc.get("type", "post"),
            "page": "api_v1_post",
            "path": request.path,
        })

    post_data = serialize_post(doc, resolve_embedded=True, posts_collection=col)
    return jsonify({
        "status": "success",
        "post": post_data,
    })


@api_v1.route("/posts/<post_id>/comments", methods=["GET"])
def get_post_comments(post_id):
    """Retrieve comments for a specific post."""
    post = _posts_collection().find_one({"post_id": post_id})
    if not post or not _can_view_draft(post):
        return jsonify({"status": "error", "message": "Post not found"}), 404

    comments_col = _comments_collection()
    cursor = comments_col.find({"post_id": post_id}).sort("timestamp", 1)
    comments = [serialize_comment(c) for c in cursor]

    return jsonify({
        "status": "success",
        "post_id": post_id,
        "count": len(comments),
        "comments": comments,
    })


@api_v1.route("/posts/<post_id>/comments", methods=["POST"])
def add_post_comment(post_id):
    """Post a new comment. Accepts JSON: { "name": "...", "body": "..." } or form."""
    posts_col = _posts_collection()
    if not posts_col.find_one({"post_id": post_id}):
        return jsonify({"status": "error", "message": "Post not found"}), 404

    data = request.get_json(silent=True) or request.form

    # Honeypot check
    if data.get("website", "").strip():
        return jsonify({"status": "error", "message": "Comment rejected"}), 400

    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"status": "error", "message": "Comment body cannot be empty"}), 400

    name = (data.get("name") or "").strip()[:60] or "Anonymous"
    clean_body = body[:2000]
    ts = content.now_str()

    comment_doc = {
        "post_id": post_id,
        "name": name,
        "body": clean_body,
        "timestamp": ts,
    }

    comments_col = _comments_collection()
    res = comments_col.insert_one(comment_doc)
    comment_doc["_id"] = res.inserted_id

    analytics.record_analytics({"event": "comments", "post_id": post_id})

    return jsonify({
        "status": "success",
        "message": "Comment posted successfully",
        "comment": serialize_comment(comment_doc),
    }), 201


@api_v1.route("/posts/<post_id>/react", methods=["POST"])
def react_to_post(post_id):
    """Add a reaction to a post.

    Accepts JSON: { "type": "like" | "heart" | "fire" | "clap" | "insightful" }
    or query parameter ?type=heart.
    """
    posts_col = _posts_collection()
    data = request.get_json(silent=True) or request.form or {}
    reaction = (data.get("type") or request.args.get("type") or "like").lower()

    allowed = {"like", "heart", "fire", "clap", "insightful"}
    if reaction not in allowed:
        reaction = "like"

    update = {"$inc": {f"reactions.{reaction}": 1, "likes": 1}}
    updated = posts_col.find_one_and_update(
        {"post_id": post_id},
        update,
        return_document=True,
    )

    if not updated:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    analytics.record_analytics({
        "event": "likes",
        "post_id": post_id,
        "reaction": reaction,
    })

    serialized = serialize_post(updated)
    return jsonify({
        "status": "success",
        "post_id": post_id,
        "likes": serialized["likes"],
        "reactions": serialized["reactions"],
    })


@api_v1.route("/posts/<post_id>/share", methods=["POST"])
def share_post(post_id):
    """Increment share count for a post."""
    posts_col = _posts_collection()
    data = request.get_json(silent=True) or request.form or {}
    platform = (data.get("platform") or request.args.get("platform") or "unknown").strip()

    updated = posts_col.find_one_and_update(
        {"post_id": post_id},
        {"$inc": {"shares": 1}},
        return_document=True,
    )

    if not updated:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    analytics.record_analytics({
        "event": "shares",
        "post_id": post_id,
        "method": platform,
    })

    return jsonify({
        "status": "success",
        "post_id": post_id,
        "shares": int(updated.get("shares") or 1),
    })


@api_v1.route("/articles", methods=["GET"])
def get_articles():
    """Convenience endpoint returning only long-form articles."""
    # Redirect internally by setting type=article in query parameters
    col = _posts_collection()
    query = {"type": "article", "$or": [{"status": "published"}, {"status": {"$exists": False}}]}
    cursor = col.find(query).sort("timestamp", -1)
    articles = [serialize_post(a, resolve_embedded=False) for a in cursor]

    return jsonify({
        "status": "success",
        "count": len(articles),
        "articles": articles,
    })


@api_v1.route("/tags", methods=["GET"])
def get_tags():
    """List of all tags used across published posts with counts."""
    col = _posts_collection()
    pipeline = [
        {"$match": {"$or": [{"status": "published"}, {"status": {"$exists": False}}]}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ]
    results = list(col.aggregate(pipeline))
    tags = [{"tag": r["_id"], "count": r["count"]} for r in results if r["_id"]]

    return jsonify({
        "status": "success",
        "count": len(tags),
        "tags": tags,
    })
