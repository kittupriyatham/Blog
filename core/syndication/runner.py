"""Background syndication runner (POSSE publish queue).

Moved here from app.py: `run_syndication()` does the work and
`enqueue_syndication()` marks the platforms `queued` on the doc, then hands the
job to a single daemon worker thread. Importing this module has no side effects -
`start_worker()` (called once from app.py) is what starts the thread, exactly
like the old module-level `threading.Thread(...).start()` in app.py.

The posts collection is resolved inside the functions: connect_db() runs in
app.py, so no import here may touch the database.
"""
import queue
import re
import threading
import time
import hashlib
from datetime import datetime, timedelta, timezone

from core import syndication
from core.config import MEDIA_FOLDER
from core.content.helpers import now_str
from core.db import Post
from core.notify import notify_telegram

MAX_ATTEMPTS = 3
RETRY_DELAYS = (5, 30)
PROCESSING_LEASE_SECONDS = 15 * 60


def _idempotency_key(doc_id, url, platform):
    value = "%s|%s|%s" % (doc_id, url, platform)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stale_before():
    return (datetime.now(timezone.utc) - timedelta(seconds=PROCESSING_LEASE_SECONDS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _retryable_error(error):
    message = (error or "").lower()
    permanent = ("not configured", "no active", "validation", "needs an image",
                 "needs a video", "requires the full article", "not signed in",
                 "missing", "unknown platform")
    if any(fragment in message for fragment in permanent):
        return False
    transient = ("timeout", "timed out", "temporarily", "connection", "502",
                 "503", "504", "429", "rate limit", "http 408")
    return any(fragment in message for fragment in transient)


def _set_platform_state(posts_collection, doc_id, platform, state, **fields):
    update = {"$set": {"syndications.$[syn].status": state}}
    for key, value in fields.items():
        update["$set"]["syndications.$[syn]." + key] = value
    posts_collection.update_one(
        {"post_id": doc_id},
        update,
        array_filters=[{"syn.platform": platform}],
    )


def _resolve_preview_placeholder_link(text: str, canonical_url: str) -> str:
    """Replace preview-only placeholder post/article links or draft links with the real canonical URL."""
    if not text or not canonical_url:
        return text
    # Match any placeholder pattern:
    # 1. /post/xxxxxxxx or /post/draft_... or http(s)://.../post/xxxxxxxx or http(s)://.../post/draft_...
    # 2. /article/xxxxxxxx or /article/draft_... or http(s)://.../article/xxxxxxxx or http(s)://.../article/draft_...
    pattern = r"(?:https?://[^\s/\"'()]+)?/(?:post|article)/(?:(?:post_|article_)?[xX]{8}|draft_[a-zA-Z0-9_-]+)"
    return re.sub(pattern, canonical_url, text)


def run_syndication(doc_id, url, platforms):
    """Publish a doc to each platform, recording the resulting URL on the doc."""
    posts_collection = Post._get_collection()
    doc = posts_collection.find_one({"post_id": doc_id})
    if not doc:
        return []
    media = syndication.media_for(doc)
    already = {s.get("platform") for s in doc.get("syndications", []) if s.get("status") == "posted"}
    results = []
    for pid in platforms:
        if pid in already:
            continue
        # Composed per platform, or uses an author's custom override if supplied.
        custom_map = doc.get("custom_syndications") or {}
        custom_text = (custom_map.get(pid) or "").strip()
        limit = syndication.text_limit_for([pid])
        if custom_text:
            text = _resolve_preview_placeholder_link(custom_text, url)
            # Ensure the canonical URL or an attached link is present in the post
            has_link = bool(url and url in text)
            if not has_link:
                has_link = bool(re.search(r"https?://[^\s/\"'()]+/(?:post|article)/[a-zA-Z0-9_.-]+", text))
            if not has_link and url and syndication.is_public_url(url):
                suffix = "\n\n" + url
                if limit:
                    room = limit - len(suffix)
                    if room > 0 and len(text) > room:
                        text = syndication.truncate_on_boundary(text, room)
                text = text + suffix
            elif limit and len(text) > limit:
                # If custom text exceeds limit, truncate safely while preserving canonical URL suffix
                if url and url in text:
                    prefix_part, url_part = text.rsplit(url, 1)
                    target_room = limit - len(url) - len(url_part)
                    if target_room > 0:
                        text = syndication.truncate_on_boundary(prefix_part.rstrip(), target_room) + ("\n\n" if prefix_part.endswith("\n") else " ") + url + url_part
                    else:
                        text = syndication.truncate_on_boundary(text, limit)
                else:
                    text = syndication.truncate_on_boundary(text, limit)
        else:
            text = syndication.compose_text(doc, url, [pid])
        existing = next((s for s in doc.get("syndications", [])
                         if s.get("platform") == pid), {})
        # Instagram and Pinterest cannot publish text at all. Render a text card
        # for them instead of failing. YouTube is excluded on purpose: it needs
        # a real video, which cannot be derived from text.
        platform_media = list(media)
        if pid in syndication.TEXT_CARD_PLATFORMS and not platform_media:
            # Rendered locally; the adapter uploads it and publishes by media_id,
            # so this needs no public URL and works on a local machine.
            try:
                platform_media = [syndication.textcard.write(
                    text, MEDIA_FOLDER, doc.get("post_id") or doc_id)]
            except Exception as e:
                print("[textcard] could not render for %s: %s" % (pid, e))
        try:
            outcome = syndication.publish_detailed_to(pid, text, url, platform_media, doc)
            rec = {"platform": pid, "label": syndication.label_for(pid), "url": outcome.get("url"),
                   "remote_id": outcome.get("remote_id"), "status": "posted", "posted_at": now_str(), "error": None}
            rec["attempt"] = existing.get("attempt", 1)
            rec["idempotency_key"] = existing.get("idempotency_key") or _idempotency_key(doc_id, url, pid)
            # Auto-cleanup for YouTube: once YouTube confirms upload success,
            # save the public YouTube URL in the post record, keeping all audit logs intact.
            if pid == "youtube" and outcome.get("url"):
                yt_url = outcome.get("url")
                posts_collection.update_one(
                    {"post_id": doc_id},
                    {"$set": {"youtube.url": yt_url, "youtube.posted_at": now_str()}}
                )
                try:
                    import os
                    vpath = syndication.video_path_for(doc_id)
                    if vpath and os.path.exists(vpath):
                        os.remove(vpath)
                        print(f"[syndication] Safely deleted staging video file for {doc_id} after YouTube upload: {vpath}")
                except Exception as clean_err:
                    print(f"[syndication] Warning: failed cleaning staging video for {doc_id}: {clean_err}")
        except Exception as e:
            rec = {"platform": pid, "label": syndication.label_for(pid), "url": None,
                   "remote_id": None, "status": "failed", "posted_at": now_str(), "error": str(e)[:300],
                   "attempt": existing.get("attempt", 1),
                   "idempotency_key": existing.get("idempotency_key") or _idempotency_key(doc_id, url, pid)}
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": rec}})
        results.append(rec)
    if results:
        notify_telegram(doc, results)
    return results


def cleanup_stale_videos(max_age_days=30):
    """Periodic maintenance rule: clean up video files from static/video/
    that have already been uploaded to YouTube or are orphaned older than max_age_days (30 days).
    Runs conservatively once every 30 days so the server does practically zero redundant work.
    """
    import os
    import time
    posts_collection = Post._get_collection()
    vdir = getattr(syndication, "VIDEO_DIR", None)
    if not vdir or not os.path.exists(vdir):
        return

    now = time.time()
    max_age_seconds = max_age_days * 86400.0
    try:
        for name in os.listdir(vdir):
            if not name.startswith("video_"):
                continue
            fpath = os.path.join(vdir, name)
            try:
                # Extract post_id from 'video_<post_id>.<ext>'
                base_part = name[len("video_"):]
                post_id = base_part.rsplit(".", 1)[0] if "." in base_part else base_part
                doc = posts_collection.find_one({"post_id": post_id})
                
                # Rule 1: If YouTube URL is already recorded in DB, delete the staging file immediately
                if doc and doc.get("youtube", {}).get("url"):
                    os.remove(fpath)
                    print(f"[video-cleanup] Removed uploaded video for {post_id}: {name}")
                    continue

                # Rule 2: If the file is older than max_age_days (e.g. 30-day abandoned draft), purge it
                age_seconds = now - os.path.getmtime(fpath)
                if age_seconds > max_age_seconds:
                    os.remove(fpath)
                    print(f"[video-cleanup] Removed stale abandoned video (age {age_seconds / 86400:.1f} days): {name}")
            except Exception as e:
                print(f"[video-cleanup] Error processing {name}: {e}")
    except Exception as scan_err:
        print(f"[video-cleanup] Directory scan error: {scan_err}")


def enqueue_syndication(doc_id, url, platforms):
    """Mark platforms queued and hand the work to the background worker.
    If no external platforms were chosen (local-only publish), trigger the universal
    Telegram notification immediately.
    """
    posts_collection = Post._get_collection()
    platforms = [p for p in (platforms or []) if p]
    if not platforms:
        doc = posts_collection.find_one({"post_id": doc_id})
        if doc:
            notify_telegram(doc, results=[], post_url=url)
        return
    for pid in platforms:
        existing = next((s for s in (posts_collection.find_one(
            {"post_id": doc_id}, {"syndications": 1}) or {}).get("syndications", [])
                         if s.get("platform") == pid), None)
        if existing and existing.get("status") == "posted":
            continue
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": {
            "platform": pid, "label": syndication.label_for(pid), "url": None,
            "status": "queued", "posted_at": now_str(), "error": None,
            "attempt": 0, "idempotency_key": _idempotency_key(doc_id, url, pid)}}})
    print(f"[syndication] Enqueued {doc_id} for platforms: {platforms}")
    # Put into the single worker queue and ensure worker is running.
    # Avoid spawning a concurrent unqueued thread which races against _syndication_worker
    # and causes duplicate HTTP 409 collisions.
    start_worker()
    _syn_queue.put((doc_id, url, platforms))


_syn_queue: "queue.Queue[tuple[str, str, list[str]]]" = queue.Queue()
_worker_started = False


def _run_job(doc_id, url, platforms):
    posts_collection = Post._get_collection()
    # Claim the job before doing network I/O. This prevents the startup
    # recovery sweep from running the same queued job alongside the worker.
    claimed = posts_collection.update_one(
        {"post_id": doc_id, "syndications": {"$elemMatch": {"platform": {"$in": platforms},
                                                            "status": "queued"}}},
        {"$set": {"syndications.$[queued].status": "processing",
                  "syndications.$[queued].started_at": now_str()}},
        array_filters=[{"queued.platform": {"$in": platforms}, "queued.status": "queued"}],
    )
    if not claimed.matched_count:
        return
    try:
        print(f"[syndication] Starting job for {doc_id} on {platforms}")
        results = []
        for pid in platforms:
            final = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                _set_platform_state(posts_collection, doc_id, pid, "processing",
                                    attempt=attempt, last_attempt_at=now_str(),
                                    idempotency_key=_idempotency_key(doc_id, url, pid))
                current = run_syndication(doc_id, url, [pid])
                final = next((row for row in current if row.get("platform") == pid), None)
                if not final or final.get("status") == "posted":
                    break
                if attempt >= MAX_ATTEMPTS or not _retryable_error(final.get("error")):
                    break
                _set_platform_state(posts_collection, doc_id, pid, "queued",
                                    error=final.get("error"),
                                    next_retry_at=now_str())
                time.sleep(RETRY_DELAYS[attempt - 1])
            if final:
                results.append(final)
        print(f"[syndication] Completed job for {doc_id}: {results}")
    except Exception as e:
        print(f"[syndication] Error executing job for {doc_id}: {e}")
        posts_collection.update_many(
            {"post_id": doc_id, "syndications": {"$elemMatch": {"platform": {"$in": platforms},
                                                                "status": "processing"}}},
            {"$set": {"syndications.$[processing].status": "failed",
                      "syndications.$[processing].error": str(e)[:300],
                      "syndications.$[processing].posted_at": now_str()}},
            array_filters=[{"processing.platform": {"$in": platforms},
                            "processing.status": "processing"}],
        )


def _syndication_worker():
    last_cleanup = 0.0
    # 30 days in seconds: 30 * 24 * 3600 = 2,592,000 seconds
    THIRTY_DAYS = 30 * 86400.0
    while True:
        try:
            # Drain tasks or timeout after 60s to check maintenance timers
            doc_id, url, platforms = _syn_queue.get(timeout=60)
            try:
                _run_job(doc_id, url, platforms)
            finally:
                _syn_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            print("[syndication] queue error:", e)

        # Run maintenance sweep conservatively once every 30 days
        now = time.time()
        # A daemon thread can be lost during a transient runtime failure. Keep
        # queued records recoverable instead of requiring a full app restart.
        try:
            recover_stuck_syndications()
        except Exception as err:
            print("[syndication] Periodic recovery error:", err)
        if now - last_cleanup > THIRTY_DAYS:
            try:
                cleanup_stale_videos(max_age_days=30)
            except Exception as err:
                print("[video-cleanup] Periodic cleanup error:", err)
            last_cleanup = now


def recover_stuck_syndications():
    """Find any posts or articles in MongoDB left with status 'queued' (e.g. from server restarts)
    and resume them.
    """
    try:
        posts_collection = Post._get_collection()
        stuck_docs = list(posts_collection.find({
            "$or": [
                {"syndications.status": "queued"},
                {"syndications": {"$elemMatch": {
                    "status": "processing",
                    "started_at": {"$lt": _stale_before()},
                }}},
            ]
        }))
        for doc in stuck_docs:
            pid = doc.get("post_id")
            if not pid:
                continue
            ptype = doc.get("type") or "post"
            from core import content
            from core.config import SITE_URL
            base = (SITE_URL or "").rstrip("/") or "https://blog.potluri-krishna-priyatham.tech"
            try:
                if ptype == "article":
                    url = content.canonical("article_detail", article_id=pid)
                else:
                    url = content.canonical("post_detail", post_id=pid)
            except Exception:
                url = f"{base}/{'article' if ptype == 'article' else 'post'}/{pid}"
            queued_platforms = [
                s.get("platform") for s in doc.get("syndications", [])
                if s.get("platform") and (
                    s.get("status") == "queued"
                    or (s.get("status") == "processing"
                        and (s.get("started_at") or "") < _stale_before())
                )
            ]
            if queued_platforms:
                posts_collection.update_one(
                    {"post_id": pid},
                    {"$set": {"syndications.$[syn].status": "queued",
                              "syndications.$[syn].error": "Recovered after worker interruption.",
                              "syndications.$[syn].started_at": None}},
                    array_filters=[{"syn.platform": {"$in": queued_platforms},
                                    "syn.status": "processing"}],
                )
                print(f"[syndication] Recovering stranded job for {pid} on {queued_platforms}")
                threading.Thread(target=_run_job, args=(pid, url, queued_platforms), daemon=True).start()
    except Exception as err:
        print("[syndication] Error checking for stranded jobs on startup:", err)


def start_worker():
    """Start the daemon thread that drains the syndication queue and sweeps stale video files."""
    global _worker_started
    if _worker_started:
        return
    threading.Thread(target=_syndication_worker, daemon=True).start()
    threading.Thread(target=recover_stuck_syndications, daemon=True).start()
    _worker_started = True
