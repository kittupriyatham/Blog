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

from src import syndication
from src.config import MEDIA_FOLDER
from src.content.helpers import now_str
from src.db import Post
from src.notify import notify_telegram


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
        except Exception as e:
            rec = {"platform": pid, "label": syndication.label_for(pid), "url": None,
                   "remote_id": None, "status": "failed", "posted_at": now_str(), "error": str(e)[:300]}
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": rec}})
        results.append(rec)
    if results:
        notify_telegram(doc, results)
    return results


def enqueue_syndication(doc_id, url, platforms):
    """Mark platforms queued and hand the work to the background worker."""
    posts_collection = Post._get_collection()
    platforms = [p for p in (platforms or []) if p]
    if not platforms:
        return
    for pid in platforms:
        posts_collection.update_one({"post_id": doc_id}, {"$pull": {"syndications": {"platform": pid}}})
        posts_collection.update_one({"post_id": doc_id}, {"$push": {"syndications": {
            "platform": pid, "label": syndication.label_for(pid), "url": None, "status": "queued", "posted_at": now_str(), "error": None}}})
    _syn_queue.put((doc_id, url, platforms))


_syn_queue: "queue.Queue[tuple[str, str, list[str]]]" = queue.Queue()
_worker_started = False


def _syndication_worker():
    while True:
        doc_id, url, platforms = _syn_queue.get()
        try:
            run_syndication(doc_id, url, platforms)
        except Exception as e:
            print("[syndication] error:", e)
        finally:
            _syn_queue.task_done()


def start_worker():
    """Start the daemon thread that drains the syndication queue (once)."""
    global _worker_started
    if _worker_started:
        return
    threading.Thread(target=_syndication_worker, daemon=True).start()
    _worker_started = True
