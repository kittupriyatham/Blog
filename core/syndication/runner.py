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
import threading

from core import syndication
from core.config import MEDIA_FOLDER
from core.content.helpers import now_str
from core.db import Post
from core.notify import notify_telegram


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
        # Composed per platform. A single shared string had to satisfy the
        # smallest limit in the batch, so Bluesky's 300 characters truncated a
        # post that Facebook would happily have taken in full.
        text = syndication.compose_text(doc, url, [pid])
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
                   "remote_id": None, "status": "failed", "posted_at": now_str(), "error": str(e)[:300]}
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
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": {
            "platform": pid, "label": syndication.label_for(pid), "url": None, "status": "queued", "posted_at": now_str(), "error": None}}})
    _syn_queue.put((doc_id, url, platforms))


_syn_queue: "queue.Queue[tuple[str, str, list[str]]]" = queue.Queue()
_worker_started = False


def _syndication_worker():
    import time
    last_cleanup = 0.0
    # 30 days in seconds: 30 * 24 * 3600 = 2,592,000 seconds
    THIRTY_DAYS = 30 * 86400.0
    while True:
        try:
            # Drain tasks or timeout after 60s to check maintenance timers
            doc_id, url, platforms = _syn_queue.get(timeout=60)
            try:
                run_syndication(doc_id, url, platforms)
            except Exception as e:
                print("[syndication] error:", e)
            finally:
                _syn_queue.task_done()
        except queue.Empty:
            pass

        # Run maintenance sweep conservatively once every 30 days
        now = time.time()
        if now - last_cleanup > THIRTY_DAYS:
            try:
                cleanup_stale_videos(max_age_days=30)
            except Exception as err:
                print("[video-cleanup] Periodic cleanup error:", err)
            last_cleanup = now


def start_worker():
    """Start the daemon thread that drains the syndication queue and sweeps stale video files."""
    global _worker_started
    if _worker_started:
        return
    threading.Thread(target=_syndication_worker, daemon=True).start()
    _worker_started = True
