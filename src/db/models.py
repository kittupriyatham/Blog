"""MongoDB document models (MongoEngine ODM <-> MongoDB).

These are the data classes the rest of the app reads/writes instead of raw
pymongo collection calls. `connect_db()` + `ensure_schema()` (see __init__.py)
create the collections and indexes on first run; later runs reuse them - this is
what `dbinit.py` used to do by hand, so it is no longer needed.

MongoEngine adds a default `id` (ObjectId) mapped to Mongo's `_id`. We do NOT use
it as the primary key: every document is still looked up by its own `post_id`.
Existing rows keep their `_id`; no data migration is required.
"""
from mongoengine import Document, DictField, IntField, ListField, StringField


class Post(Document):
    # unique-but-non-sparse matches the index dbinit.py already created on
    # `blog_db.posts` (post_id_1, unique), so MongoEngine's auto ensure_indexes
    # is idempotent instead of colliding on the shared index name. post_id is
    # always present (generate_post_id guarantees it), so a non-sparse unique
    # index is correct and lets the model own the schema.
    post_id = StringField(required=True, unique=True)
    type = StringField()
    status = StringField()
    timestamp = StringField()
    likes = IntField(default=0)
    views = IntField(default=0)
    title = StringField()
    cover_image = StringField()
    tags = ListField(StringField())
    blocks = ListField(DictField())
    syndications = ListField(DictField())
    # YouTube upload metadata collected by the /youtube/<post_id> page
    # (title/description/visibility/tags/category_id/... and the stored video
    # filename). Declared so the schema is explicit; strict=False means a
    # raw-collection $set also works without tripping MongoEngine.
    youtube = DictField()
    # Each social platform's own engagement counts, cached by the analytics
    # refresh route (POST /admin/analytics/refresh) so the dashboard never has to
    # call SocialAPI to render. Keyed by platform slug -> {likes, comments,
    # views, permalink, synced_at, ...}, with a reserved `_meta` key holding the
    # fetch timestamp and any errors. See src/syndication/socialapi_metrics.py.
    platform_metrics = DictField()

    meta = {
        "collection": "posts",
        "strict": False,  # keep arbitrary/legacy fields untouched
        "indexes": ["post_id", "type", "status", "timestamp"],
        "ordering": ["-timestamp"],
    }


class Comment(Document):
    post_id = StringField(required=True)
    name = StringField()
    body = StringField()
    timestamp = StringField()

    meta = {
        "collection": "comments",
        "strict": False,
        "indexes": ["post_id", "timestamp"],
        "ordering": ["timestamp"],
    }


class AnalyticsEvent(Document):
    event_id = StringField()
    event = StringField()
    ts = StringField()
    ip_hash = StringField()

    meta = {
        "collection": "analytics",
        "strict": False,  # event payloads vary by type (geo, time_spent, shares, ...)
        "indexes": ["event", "ts", "ip_hash", "event_id"],
    }
