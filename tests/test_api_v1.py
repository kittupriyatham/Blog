"""Integration tests for the /api/v1 REST endpoints and existing web routes."""

import pytest
import mongomock
from unittest.mock import patch

from app import app
from core.api.v1 import posts as posts_module
from core.api.v1.serializers import serialize_post


@pytest.fixture
def mock_db():
    client = mongomock.MongoClient()
    db = client.test_blog_db
    posts_col = db.posts
    comments_col = db.comments

    # Seed test data
    posts_col.insert_many([
        {
            "post_id": "test_post_1",
            "type": "post",
            "status": "published",
            "title": "Quantum Computing Introduction",
            "content": "This is a test post about quantum algorithms.",
            "tags": ["quantum", "algorithms"],
            "timestamp": "2026-11-01 10:00:00",
            "likes": 5,
            "views": 12,
            "reactions": {"like": 5, "heart": 2, "fire": 1, "clap": 0, "insightful": 0},
            "blocks": [{"type": "text", "content": "This is a test post about quantum algorithms."}],
        },
        {
            "post_id": "test_article_1",
            "type": "article",
            "status": "published",
            "title": "Distributed Systems at Scale",
            "content": "In-depth article about distributed systems.",
            "cover_image": "https://example.com/cover.webp",
            "tags": ["distributed-systems", "architecture"],
            "timestamp": "2026-11-02 12:00:00",
            "likes": 10,
            "views": 45,
            "reactions": {"like": 10, "heart": 8, "fire": 4, "clap": 3, "insightful": 2},
            "blocks": [{"type": "text", "content": "In-depth article about distributed systems."}],
        },
        {
            "post_id": "draft_post_1",
            "type": "post",
            "status": "draft",
            "title": "Draft Post",
            "content": "This should not be publicly visible.",
            "timestamp": "2026-11-03 08:00:00",
        }
    ])

    comments_col.insert_one({
        "post_id": "test_post_1",
        "name": "Alice",
        "body": "Fascinating quantum article!",
        "timestamp": "2026-11-01 11:00:00",
    })

    return posts_col, comments_col


@pytest.fixture
def client(mock_db):
    posts_col, comments_col = mock_db
    app.config["TESTING"] = True

    with patch.object(posts_module, "_posts_collection", return_value=posts_col), \
         patch.object(posts_module, "_comments_collection", return_value=comments_col), \
         patch("app.posts_collection", posts_col), \
         patch("app.comments_collection", comments_col):
        with app.test_client() as c:
            yield c


def test_get_posts_list(client):
    """Test GET /api/v1/posts pagination and response structure."""
    res = client.get("/api/v1/posts")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["total"] == 2  # Only published posts (excludes draft)
    assert len(data["posts"]) == 2
    assert data["posts"][0]["post_id"] in ("test_post_1", "test_article_1")


def test_demo_cannot_list_original_drafts(client):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["is_demo"] = True

    res = client.get("/api/v1/posts?status=all")
    assert res.status_code == 200
    assert res.get_json()["total"] == 2


def test_get_posts_filter_type(client):
    """Test filtering posts by type=article."""
    res = client.get("/api/v1/posts?type=article")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["posts"][0]["post_id"] == "test_article_1"


def test_get_posts_filter_tag(client):
    """Test filtering posts by tag."""
    res = client.get("/api/v1/posts?tag=quantum")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 1
    assert data["posts"][0]["post_id"] == "test_post_1"


def test_get_post_detail_success(client):
    """Test GET /api/v1/posts/<post_id> for an existing post."""
    res = client.get("/api/v1/posts/test_post_1")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["post"]["post_id"] == "test_post_1"
    assert data["post"]["title"] == "Quantum Computing Introduction"
    assert data["post"]["reactions"]["like"] == 5


def test_get_post_detail_draft_hidden(client):
    """Drafts must return 404 for non-logged in users."""
    res = client.get("/api/v1/posts/draft_post_1")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"


def test_demo_cannot_read_original_draft(client):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["is_demo"] = True

    res = client.get("/api/v1/posts/draft_post_1")
    assert res.status_code == 404


def test_get_comments_draft_hidden(client):
    """Comments for drafts must return 404 for non-logged in users."""
    res = client.get("/api/v1/posts/draft_post_1/comments")
    assert res.status_code == 404
    data = res.get_json()
    assert data["status"] == "error"


def test_get_post_detail_not_found(client):
    """Non-existent post returns 404."""
    res = client.get("/api/v1/posts/does_not_exist")
    assert res.status_code == 404


def test_embedded_draft_article_is_hidden():
    collection = mongomock.MongoClient().test_blog_db.posts
    collection.insert_many([
        {
            "post_id": "published_post",
            "type": "post",
            "content": "/article/draft_article",
        },
        {
            "post_id": "draft_article",
            "type": "article",
            "status": "draft",
            "title": "Secret article",
        },
    ])

    data = serialize_post(
        collection.find_one({"post_id": "published_post"}),
        resolve_embedded=True,
        posts_collection=collection,
    )
    assert data["embedded_article"] is None


def test_get_comments(client):
    """Test GET /api/v1/posts/<post_id>/comments."""
    res = client.get("/api/v1/posts/test_post_1/comments")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert data["comments"][0]["name"] == "Alice"
    assert data["comments"][0]["body"] == "Fascinating quantum article!"


def test_add_comment(client):
    """Test POST /api/v1/posts/<post_id>/comments."""
    payload = {"name": "Bob", "body": "Great insights!"}
    res = client.post("/api/v1/posts/test_post_1/comments", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert data["comment"]["name"] == "Bob"
    assert data["comment"]["body"] == "Great insights!"

    # Verify it now shows in comments list
    res2 = client.get("/api/v1/posts/test_post_1/comments")
    assert res2.get_json()["count"] == 2


def test_react_to_post(client):
    """Test POST /api/v1/posts/<post_id>/react."""
    with patch.object(posts_module.analytics, "record_analytics") as record_analytics:
        res = client.post("/api/v1/posts/test_post_1/react", json={"type": "heart"})

    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["reactions"]["heart"] == 3
    assert data["likes"] == 6
    record_analytics.assert_called_once_with({
        "event": "likes",
        "post_id": "test_post_1",
        "reaction": "heart",
    })


def test_share_post_records_dashboard_event(client):
    """Share analytics use the event shape consumed by dashboard aggregation."""
    with patch.object(posts_module.analytics, "record_analytics") as record_analytics:
        res = client.post("/api/v1/posts/test_post_1/share", json={"platform": "whatsapp"})

    assert res.status_code == 200
    assert res.get_json()["shares"] == 1
    record_analytics.assert_called_once_with({
        "event": "shares",
        "post_id": "test_post_1",
        "method": "whatsapp",
    })


def test_get_articles(client):
    """Test GET /api/v1/articles."""
    res = client.get("/api/v1/articles")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["count"] == 1
    assert data["articles"][0]["post_id"] == "test_article_1"


def test_get_tags(client):
    """Test GET /api/v1/tags."""
    res = client.get("/api/v1/tags")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    tag_names = [t["tag"] for t in data["tags"]]
    assert "quantum" in tag_names
    assert "distributed-systems" in tag_names


def test_get_author(client):
    """Test GET /api/v1/author returns author profile."""
    res = client.get("/api/v1/author")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert "Potluri Krishna Priyatham" in data["author"]["name"]
    assert "urls" in data["author"]
    assert "domains" in data["author"]


def test_existing_web_routes_regression(client):
    """Ensure existing HTML web routes still render properly."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"<!DOCTYPE html>" in res.data or b"<html" in res.data

    res_author = client.get("/author")
    assert res_author.status_code == 200
    assert b"Potluri Krishna Priyatham" in res_author.data


def test_create_post_unauthorized(client):
    """Test POST /api/v1/posts rejects unauthenticated callers."""
    res = client.post("/api/v1/posts", json={"content": "Hello unauth world"})
    assert res.status_code == 401
    assert res.get_json()["status"] == "error"


def test_create_post_success(client):
    """Test POST /api/v1/posts successfully creates a post when logged in."""
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"
        sess["is_demo"] = False

    res = client.post("/api/v1/posts", json={
        "title": "Mobile Announcement",
        "content": "Posted straight from the Android app!",
        "tags": ["mobile", "android"],
        "type": "post"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["status"] == "success"
    assert data["post"]["title"] == "Mobile Announcement"
    assert "Android app" in data["post"]["content"]
    assert "mobile" in data["post"]["tags"]
    assert data["post"]["type"] == "post"


def test_create_post_empty_content(client):
    """Test POST /api/v1/posts rejects empty content."""
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"
        sess["is_demo"] = False

    res = client.post("/api/v1/posts", json={"content": "  "})
    assert res.status_code == 400
    assert res.get_json()["status"] == "error"

