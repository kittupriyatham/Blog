"""REST API endpoints for Posts, Articles, Comments, Reactions, and Tags."""

import math
from flask import Blueprint, jsonify, request, session
from core.db import Comment, Post
from core import analytics, content
from core.api.v1.serializers import serialize_comment, serialize_post

api_v1 = Blueprint("api_v1", __name__)


def _posts_collection():
    return Post._get_collection()


def _comments_collection():
    return Comment._get_collection()


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

    # Admin view includes drafts if logged in
    if session.get("logged_in") and request.args.get("status") == "all":
        query = {}

    filters = [query]

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


@api_v1.route("/posts/<post_id>", methods=["GET"])
def get_post_detail(post_id):
    """Get single post or article by post_id."""
    col = _posts_collection()
    doc = col.find_one({"post_id": post_id})

    if not doc:
        return jsonify({"status": "error", "message": "Post not found"}), 404

    if doc.get("status") == "draft" and not session.get("logged_in"):
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
        "event": "like",
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
        "event": "share",
        "post_id": post_id,
        "platform": platform,
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
