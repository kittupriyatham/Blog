"""REST API endpoints for Posts, Articles, Comments, Reactions, and Tags."""

import math
from flask import Blueprint, current_app, jsonify, request, session
from core.api.v1.auth import _mobile_request
from core.config import SITE_URL
from core.db import Comment, Post
from core import analytics, content, media, syndication
from core.syndication import runner
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


def _demo_syndication_url(platform: str, kind: str, doc_id: str) -> str:
    base = (SITE_URL or "").rstrip("/")
    if not base:
        try:
            base = request.host_url.rstrip("/")
        except Exception:
            base = "https://blog.potluri-krishna-priyatham.tech"
    doc_id_str = str(doc_id).strip()
    target = doc_id_str if doc_id_str.startswith(f"{kind}_") else f"{kind}_{doc_id_str}"
    return f"{base}/example/{platform}/{target}"


@api_v1.route("/syndication/platforms", methods=["GET"])
def get_syndication_platforms():
    """Return available syndication platforms for the mobile composer."""
    kind = (request.args.get("kind") or "post").strip().lower()
    if kind not in ("post", "article"):
        kind = "post"
    platforms = syndication.available_platforms(kind=kind)
    return jsonify({
        "status": "success",
        "kind": kind,
        "platforms": platforms,
    })


@api_v1.route("/media", methods=["POST"])
def upload_media_v1():
    """Upload a media or document attachment for a post from the mobile app or API."""
    if not session.get("logged_in") and not media.upload_authorized():
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    if not (session.get("mobile_authenticated") and _mobile_request()):
        if not media.upload_authorized() or session.get("logged_in"):
            # Only require CSRF for browser sessions without mobile_authenticated
            current_app.extensions["csrf"].protect()

    f = request.files.get("file") or request.files.get("media")
    if not f or not f.filename:
        return jsonify({"status": "error", "message": "No file provided."}), 400
    if not media.allowed_file(f.filename):
        return jsonify({"status": "error", "message": "Unsupported file type."}), 400

    post_id = (request.form.get("post_id") or "").strip() or media.generate_post_id(posts_collection=_posts_collection())
    url = media.upload_to_server(f, media.media_stem(post_id), set())
    return jsonify({
        "status": "success",
        "post_id": post_id,
        "url": url,
        "name": url.rsplit("/", 1)[-1],
    }), 201


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
      - content: string (required unless media_paths is non-empty)
      - type: 'post' | 'article' (default: 'post')
      - tags: list[str] or comma-separated string
      - status: 'published' | 'draft' (default: 'published')
      - media_paths: list[str] (optional uploaded media URLs)
      - platforms: list[str] or comma-separated string (optional syndication platform IDs)
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

    media_raw = data.get("media_paths") or []
    if isinstance(media_raw, str):
        media_paths = [m.strip() for m in media_raw.split(",") if m.strip()]
    elif isinstance(media_raw, list):
        media_paths = [str(m).strip() for m in media_raw if isinstance(m, str) and m.strip()]
    else:
        return jsonify({"status": "error", "message": "media_paths must be a list of strings."}), 400

    platforms_raw = data.get("platforms") or []
    if isinstance(platforms_raw, str):
        platforms = [p.strip() for p in platforms_raw.split(",") if p.strip()]
    elif isinstance(platforms_raw, list):
        platforms = [str(p).strip() for p in platforms_raw if isinstance(p, str) and p.strip()]
    else:
        return jsonify({"status": "error", "message": "platforms must be a list of strings."}), 400

    content_body = (data.get("content") or data.get("body") or "").strip()
    if not content_body and not media_paths:
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

    blocks = []
    if content_body:
        blocks.append({"type": "text", "content": content_body})
    if media_paths:
        blocks.append({"type": "media", "media_paths": media_paths})

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

    valid_platforms = [p for p in platforms if p != "youtube" and syndication.get(p) is not None]
    if post_status == "published" and valid_platforms and is_demo:
        demo_syndications = []
        for p in valid_platforms:
            demo_syndications.append({
                "platform": p,
                "label": syndication.label_for(p),
                "url": _demo_syndication_url(p, post_type, post_id),
                "remote_id": f"demo_{p}_{post_id}",
                "status": "posted",
                "posted_at": now,
                "error": None,
            })
        if demo_syndications:
            new_post["syndications"] = demo_syndications

    res = col.insert_one(new_post)
    new_post["_id"] = res.inserted_id

    if post_status == "published" and valid_platforms and not is_demo:
        canonical_endpoint = "article_detail" if post_type == "article" else "post_detail"
        runner.enqueue_syndication(
            post_id,
            content.canonical(canonical_endpoint, post_id=post_id),
            valid_platforms,
        )

    analytics.record_analytics({
        "event": "create_post",
        "post_id": post_id,
        "type": post_type,
        "is_demo": is_demo,
    })

    serialized = serialize_post(new_post, resolve_embedded=True, posts_collection=col)
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
