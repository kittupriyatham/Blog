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


def test_admin_all_posts_includes_demo_while_public_feed_excludes_it(client, mock_db):
    posts_col, _ = mock_db
    posts_col.insert_many([
        {"post_id": "demo_published", "type": "post", "status": "published",
         "is_demo": True, "tags": ["demo"], "timestamp": "2026-11-04"},
        {"post_id": "demo_draft", "type": "post", "status": "draft",
         "is_demo": True, "tags": ["demo"], "timestamp": "2026-11-05"},
    ])

    def ids(path):
        response = client.get(path)
        assert response.status_code == 200
        return {post["post_id"] for post in response.get_json()["posts"]}

    assert ids("/api/v1/posts?status=all") == {"test_post_1", "test_article_1"}
    with client.session_transaction() as session:
        session.update(logged_in=True, is_demo=True)
    assert ids("/api/v1/posts") == {"test_post_1", "test_article_1", "demo_published"}
    assert ids("/api/v1/posts?status=all") == {
        "test_post_1", "test_article_1", "demo_published", "demo_draft"
    }
    with client.session_transaction() as session:
        session.update(logged_in=True, is_demo=False)
    assert ids("/api/v1/posts?status=all") == {
        "test_post_1", "test_article_1", "draft_post_1", "demo_published", "demo_draft"
    }
    assert ids("/api/v1/posts?status=all&tag=demo") == {"demo_published", "demo_draft"}


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
        sess["mobile_authenticated"] = True

    res = client.post("/api/v1/posts", headers={"X-Mobile-Client": "blog-android"}, json={
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
        sess["mobile_authenticated"] = True

    res = client.post("/api/v1/posts", json={"content": "  "},
                      headers={"X-Mobile-Client": "blog-android"})
    assert res.status_code == 400
    assert res.get_json()["status"] == "error"


@pytest.mark.parametrize("title", [None, "", "   "])
@pytest.mark.parametrize("status", [None, "published", "invalid"])
def test_published_article_requires_title(client, mock_db, title, status):
    with client.session_transaction() as sess:
        sess.update(logged_in=True, is_demo=False, mobile_authenticated=True)
    payload = {"type": " ARTICLE ", "content": "Article content"}
    if title is not None:
        payload["title"] = title
    if status is not None:
        payload["status"] = status

    posts_col, _ = mock_db
    count = posts_col.count_documents({})
    with patch.object(posts_module.analytics, "record_analytics") as record:
        response = client.post("/api/v1/posts", json=payload,
                               headers={"X-Mobile-Client": "blog-android"})
    assert response.status_code == 400
    assert response.get_json()["message"] == "Article title is required to publish."
    assert posts_col.count_documents({}) == count
    record.assert_not_called()


@pytest.mark.parametrize("post_type,status,title", [
    ("article", "published", "  A title  "),
    ("article", "draft", ""),
    ("post", "published", ""),
])
def test_create_post_title_rules_preserve_other_publications(client, mock_db, post_type, status, title):
    with client.session_transaction() as sess:
        sess.update(logged_in=True, is_demo=False, mobile_authenticated=True)
    with patch.object(posts_module.analytics, "record_analytics"):
        response = client.post("/api/v1/posts", json={
            "type": post_type, "status": status, "title": title, "content": "Content"
        }, headers={"X-Mobile-Client": "blog-android"})
    assert response.status_code == 201
    assert response.get_json()["post"]["title"] == title.strip()
    posts_col, _ = mock_db
    assert posts_col.find_one({"post_id": response.get_json()["post"]["post_id"]})["status"] == status


@pytest.mark.parametrize("payload", [[], [1], "text", 2, None] + [
    {"content": "valid", field: value}
    for field in ("content", "body", "title", "type", "status")
    for value in ([], {}, 1, True, None)
])
def test_create_post_rejects_invalid_types(client, payload):
    with client.session_transaction() as sess:
        sess.update(logged_in=True, is_demo=False, mobile_authenticated=True)
    import json
    response = client.post("/api/v1/posts", data=json.dumps(payload),
                           content_type="application/json",
                           headers={"X-Mobile-Client": "blog-android"})
    assert response.status_code == 400


def test_browser_creation_requires_csrf_and_accepts_valid_token(client):
    from flask_wtf.csrf import generate_csrf
    with client.session_transaction() as sess:
        sess.update(logged_in=True, is_demo=False)
    assert client.post("/api/v1/posts", data={"content": "blocked"}).status_code == 400
    # A mobile header alone must not bypass browser session protection.
    assert client.post("/api/v1/posts", json={"content": "blocked"},
                       headers={"X-Mobile-Client": "blog-android"}).status_code == 400
    with app.test_request_context():
        token = generate_csrf()
        from flask import session
        raw_token = session["csrf_token"]
    with client.session_transaction() as sess:
        sess["csrf_token"] = raw_token
    response = client.post("/api/v1/posts", data={
        "content": "Article", "type": "article", "csrf_token": token,
    })
    assert response.status_code == 400
    assert response.get_json()["message"] == "Article title is required to publish."
    with patch.object(posts_module.analytics, "record_analytics"):
        response = client.post("/api/v1/posts", data={"body": " fallback ", "tags": "a, b", "csrf_token": token})
    assert response.status_code == 201
    assert response.get_json()["post"]["content"] == "fallback"
    assert response.get_json()["post"]["tags"] == ["a", "b"]


def test_native_login_can_publish_and_demo_feed_is_isolated(client):
    headers = {"X-Mobile-Client": "blog-android"}
    assert client.post("/api/v1/auth/login", json={"username": "demo", "password": "demo"}, headers=headers).status_code == 200
    with patch.object(posts_module.analytics, "record_analytics"):
        response = client.post("/api/v1/posts", json={"content": "demo publication"}, headers=headers)
    assert response.status_code == 201
    post_id = response.get_json()["post"]["post_id"]
    assert any(p["post_id"] == post_id for p in client.get("/api/v1/posts").get_json()["posts"])
    assert client.post("/api/v1/posts", data={"content": "form bypass"}, headers=headers).status_code == 400
    client.post("/api/v1/auth/logout", headers=headers)
    assert all(p["post_id"] != post_id for p in client.get("/api/v1/posts").get_json()["posts"])
    assert client.get("/api/v1/posts?status=all").get_json()["total"] == 2


def test_get_syndication_platforms(client):
    res = client.get("/api/v1/syndication/platforms?kind=post")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["kind"] == "post"
    assert isinstance(data["platforms"], list)
    platform_ids = {p["id"] for p in data["platforms"]}
    assert "linkedin" in platform_ids
    assert "medium" not in platform_ids


def test_upload_media_v1_and_create_post_with_attachments_and_syndication(client, mock_db):
    import io
    headers = {"X-Mobile-Client": "blog-android"}

    # Unauthenticated upload should fail
    res_unauth = client.post(
        "/api/v1/media",
        data={"file": (io.BytesIO(b"fake image"), "photo.png")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert res_unauth.status_code == 401

    with client.session_transaction() as sess:
        sess.update(logged_in=True, username="demo", is_demo=True, mobile_authenticated=True)

    # Unsupported extension should fail
    res_bad = client.post(
        "/api/v1/media",
        data={"file": (io.BytesIO(b"bad"), "malware.exe")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert res_bad.status_code == 400

    with patch.object(posts_module.media, "upload_to_server", return_value="/media/media_test123.png"):
        res_upload = client.post(
            "/api/v1/media",
            data={"file": (io.BytesIO(b"fake png"), "screenshot.png")},
            content_type="multipart/form-data",
            headers=headers,
        )
    assert res_upload.status_code == 201
    upload_data = res_upload.get_json()
    assert upload_data["status"] == "success"
    assert upload_data["url"] == "/media/media_test123.png"

    # Create post with media_paths, embedded article (/article/test_article_1), and syndication platforms in demo mode
    with patch.object(posts_module.analytics, "record_analytics"):
        res_post = client.post(
            "/api/v1/posts",
            json={
                "content": "Check out this article /article/test_article_1",
                "media_paths": ["/media/media_test123.png"],
                "platforms": ["linkedin", "twitter"],
                "tags": ["mobile", "posse"],
            },
            headers=headers,
        )
    assert res_post.status_code == 201
    created = res_post.get_json()["post"]
    assert created["media_paths"] == ["/media/media_test123.png"]
    assert created["embedded_article"] is not None
    assert created["embedded_article"]["post_id"] == "test_article_1"
    assert created["embedded_article"]["title"] == "Distributed Systems at Scale"
    syndicated_platforms = {s["platform"] for s in created["syndications"]}
    assert syndicated_platforms == {"linkedin", "twitter"}

    # Admin post creation should enqueue real syndication
    with client.session_transaction() as sess:
        sess.update(logged_in=True, username="admin", is_demo=False, mobile_authenticated=True)

    with patch.object(posts_module.analytics, "record_analytics"), \
         patch.object(posts_module.runner, "enqueue_syndication") as mock_enqueue:
        res_admin = client.post(
            "/api/v1/posts",
            json={
                "content": "",
                "media_paths": ["/media/media_test123.png"],
                "platforms": ["linkedin"],
            },
            headers=headers,
        )
    assert res_admin.status_code == 201
    admin_post = res_admin.get_json()["post"]
    assert admin_post["media_paths"] == ["/media/media_test123.png"]
    mock_enqueue.assert_called_once()
    args = mock_enqueue.call_args[0]
    assert args[0] == admin_post["post_id"]
    assert args[2] == ["linkedin"]

