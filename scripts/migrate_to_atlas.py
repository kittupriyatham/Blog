"""One-time migration: local blog -> MongoDB Atlas + Cloudflare R2.

Run this ONCE, locally, before cutting over to Render. It moves everything that
must survive off your PC:

  1. posts / comments / analytics   local mongod  ->  Atlas (MONGO_URI)
  2. the LinkedIn OAuth token       data/linkedin_token.json  ->  Atlas `secrets`
  3. media files                    media/  ->  R2, and rewrites every post's
                                    media_paths from /media/<name> to the R2 URL

It is re-runnable: every step skips records that already exist at the
destination (matched by _id), so a partial run can simply be run again.

Usage (from the repo root, with your real MONGO_URI + R2 creds in .env):

    venv\\Scripts\\python.exe scripts\\migrate_to_atlas.py

Nothing here is imported by the app - it is a throwaway tool, so it talks to
pymongo/R2 directly rather than through the app's providers.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from dotenv import load_dotenv

load_dotenv()

from pymongo import MongoClient

# Where the data lives *today* (the local mongod the app has been using).
SOURCE_URI = (
    os.environ.get("LOCAL_MONGO_URI", "").strip()
    or os.environ.get("MIGRATE_SOURCE_URI", "").strip()
    or "mongodb://127.0.0.1:27017/blog_db"
)
# Where it is going (Atlas). Read from ATLAS_MONGO_URI or MONGO_URI.
TARGET_URI = (
    os.environ.get("ATLAS_MONGO_URI", "").strip()
    or os.environ.get("MONGO_URI", "").strip()
)

COLLECTIONS = ("posts", "comments", "analytics")


def _connect(uri, label):
    if not uri:
        raise SystemExit("No URI for %s." % label)
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    # Fail fast: a typo'd Atlas string should surface here, not mid-copy.
    client.admin.command("ping")
    print("[migrate] connected to %s: %s" % (label, uri.split("@")[-1]))
    return client


def migrate_collections(source, target):
    """Copy each collection, skipping docs whose _id already exists in Atlas."""
    for name in COLLECTIONS:
        src = source[name]
        dst = target[name]
        existing = {d["_id"] for d in dst.find({}, {"_id": 1})}
        docs = [d for d in src.find({}) if d.get("_id") not in existing]
        if docs:
            dst.insert_many(docs)
        print("[migrate] %-10s copied %d (skipped %d already present)"
              % (name, len(docs), src.count_documents({}) - len(docs)))


def migrate_linkedin_token(target):
    """Move the OAuth token into Atlas `secrets`, then retire the local file."""
    from src.syndication.linkedin_token import _store_path, _TOKEN_DOC_ID

    path = _store_path()
    if not os.path.isfile(path):
        print("[migrate] linkedin token: no legacy file at %s (nothing to move)" % path)
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            token = json.load(fh)
    except (OSError, ValueError) as e:
        print("[migrate] linkedin token: could not read %s (%s) - skipped" % (path, e))
        return
    if not isinstance(token, dict) or not token:
        print("[migrate] linkedin token: legacy file empty - skipped")
        return

    target["secrets"].update_one(
        {"_id": _TOKEN_DOC_ID}, {"$set": token}, upsert=True)
    # Rename (not delete) so the migrated file remains as an audit trail / rollback.
    os.replace(path, path + ".migrated")
    print("[migrate] linkedin token: stored in secrets[%r], local file renamed to .migrated"
          % _TOKEN_DOC_ID)


def _bare_name(ref):
    return str(ref or "").replace("/media/", "").lstrip("/")


def _is_local_media(ref):
    text = str(ref or "")
    return text.startswith("/media/") or (text and not text.startswith(("http://", "https://")))


def migrate_media(target):
    """Upload media/ to R2 and rewrite every post's media_paths to the R2 URL."""
    from src.config import MEDIA_FOLDER
    from src.providers.cloud.media import get_adapter

    adapter = get_adapter("r2")
    if not adapter.health():
        print("[migrate] media: R2 is not configured (set R2_* in .env) - skipped")
        return

    class _LocalFile:
        """Minimal FileStorage stand-in: the adapter only calls .stream/.read()."""
        def __init__(self, path, name):
            self.filename = name
            self.stream = open(path, "rb")

        def read(self, *a):
            return self.stream.read(*a)

        def close(self):
            self.stream.close()

    # Pass 1: upload every file that exists on disk, name -> public URL.
    urls = {}
    if os.path.isdir(MEDIA_FOLDER):
        for name in sorted(os.listdir(MEDIA_FOLDER)):
            full = os.path.join(MEDIA_FOLDER, name)
            if not os.path.isfile(full):
                continue
            fh = _LocalFile(full, name)
            try:
                urls[name] = adapter.upload(fh, name)
            finally:
                fh.close()
    print("[migrate] media: uploaded %d files to R2" % len(urls))

    # Pass 2: rewrite media_paths in every post that references local media.
    rewritten = 0
    for post in target["posts"].find({}):
        blocks = post.get("blocks") or []
        changed = False
        for block in blocks:
            if block.get("type") != "media":
                continue
            paths = block.get("media_paths") or []
            new = []
            for ref in paths:
                if _is_local_media(ref):
                    name = _bare_name(ref)
                    if name in urls:
                        new.append(urls[name])
                        changed = True
                        continue
                new.append(ref)
            if changed:
                block["media_paths"] = new
        if changed:
            target["posts"].update_one({"_id": post["_id"]}, {"$set": {"blocks": blocks}})
            rewritten += 1
    print("[migrate] media: rewrote media_paths in %d posts" % rewritten)


def main():
    if not TARGET_URI:
        raise SystemExit("ATLAS_MONGO_URI (or MONGO_URI) is not set - put your Atlas connection string in .env first.")

    source = _connect(SOURCE_URI, "local mongod (source)")
    target = _connect(TARGET_URI, "Atlas (target)")

    migrate_collections(source, target)
    migrate_linkedin_token(target)
    migrate_media(target)

    print("\n[migrate] done. Spot-check a post page, then follow the Render cutover steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
