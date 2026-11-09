"""JSON serializers for MongoDB documents (Posts, Comments, Author)."""

from typing import Any, Dict, List, Optional
import re

POST_ID_REF_PATTERN = re.compile(r"/(?:post|article)/([a-zA-Z0-9_.-]+)")


def serialize_post(doc: Optional[Dict[str, Any]], resolve_embedded: bool = False, posts_collection=None) -> Optional[Dict[str, Any]]:
    """Converts a MongoDB Post document into a clean, JSON-serializable dictionary."""
    if not doc:
        return None

    post_id = str(doc.get("post_id") or "")
    blocks = doc.get("blocks") or []
    content = doc.get("content") or ""
    media_paths = list(doc.get("media_paths") or [])

    # Extract content and media from blocks
    if blocks:
        text_parts = []
        for b in blocks:
            if isinstance(b, dict):
                b_type = b.get("type")
                if b_type == "text" and b.get("content"):
                    text_parts.append(str(b.get("content")).strip())
                elif b_type == "media" and b.get("media_paths"):
                    for p in b.get("media_paths", []):
                        if p not in media_paths:
                            media_paths.append(p)
        if not content:
            content = "\n\n".join(text_parts)

    reactions = doc.get("reactions")
    if not isinstance(reactions, dict):
        reactions = {"like": 0, "heart": 0, "fire": 0, "clap": 0, "insightful": 0}
    else:
        reactions = dict(reactions)
        for key in ("like", "heart", "fire", "clap", "insightful"):
            reactions.setdefault(key, 0)

    # Clean syndications list
    raw_syndications = doc.get("syndications") or []
    syndications = []
    for s in raw_syndications:
        if isinstance(s, dict):
            syndications.append({
                "platform": s.get("platform"),
                "status": s.get("status"),
                "url": s.get("url") or s.get("permalink") or s.get("target_url"),
                "error": s.get("error"),
                "synced_at": s.get("synced_at") or s.get("posted_at") or s.get("timestamp"),
            })

    # Embedded article or post linking if requested
    embedded_article = None
    if resolve_embedded and posts_collection is not None and content:
        match = POST_ID_REF_PATTERN.search(content)
        if match:
            ref_id = match.group(1)
            ref_doc = posts_collection.find_one({
                "post_id": ref_id,
                "$or": [{"status": "published"}, {"status": {"$exists": False}}],
            })
            if ref_doc:
                ref_type = ref_doc.get("type") or "post"
                ref_content = ref_doc.get("content") or ""
                if not ref_content and ref_doc.get("blocks"):
                    ref_content = "\n\n".join(
                        str(b.get("content")).strip()
                        for b in ref_doc.get("blocks", [])
                        if isinstance(b, dict) and b.get("type") == "text" and b.get("content")
                    )
                default_title = "Article" if ref_type == "article" else (
                    ref_content.split("\n")[0][:80] if ref_content else "Post"
                )
                embedded_article = {
                    "post_id": ref_doc.get("post_id"),
                    "type": ref_type,
                    "title": ref_doc.get("title") or default_title,
                    "content": ref_content[:240],
                    "cover_image": ref_doc.get("cover_image") or "",
                    "timestamp": ref_doc.get("timestamp") or "",
                }

    return {
        "post_id": post_id,
        "type": doc.get("type") or "post",
        "title": doc.get("title") or "",
        "content": content,
        "cover_image": doc.get("cover_image") or "",
        "timestamp": doc.get("timestamp") or "",
        "tags": list(doc.get("tags") or []),
        "likes": int(doc.get("likes") or 0),
        "views": int(doc.get("views") or 0),
        "shares": int(doc.get("shares") or 0),
        "reactions": reactions,
        "blocks": blocks,
        "media_paths": media_paths,
        "syndications": syndications,
        "embedded_article": embedded_article,
    }


def serialize_comment(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Converts a MongoDB Comment document into a clean, JSON-serializable dictionary."""
    if not doc:
        return None

    return {
        "id": str(doc.get("_id", "")),
        "post_id": str(doc.get("post_id") or ""),
        "name": str(doc.get("name") or "Anonymous"),
        "body": str(doc.get("body") or ""),
        "timestamp": str(doc.get("timestamp") or ""),
    }
