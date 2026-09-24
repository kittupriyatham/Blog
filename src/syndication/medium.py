"""Publish to Medium by importing a publicly served copy of the article.

Medium has no write API. Driving the editor does not work either: Medium refuses
automated saves with "Something is wrong and we cannot save your story" - which
was reproduced in every mode (headless, headless+stealth, headed, a real
persistent profile, and even the interactive playwright-cli browser). Typing
into the editor succeeds; saving does not. So that route is a dead end.

What *does* work is Medium's own importer: it fetches a URL **server-side** and
creates a DRAFT. Its only requirement is that the URL be publicly reachable -
which is why it could never work against localhost.

So this module renders the article to a standalone HTML file under `media/` and
imports *that* URL. Because the file is served from the same place as the text
cards, Medium works wherever media is public - exactly the requirement Instagram
and Pinterest already have.

Config (env):
  SITE_URL           public base the media folder is served from (required)
  MEDIUM_MEDIA_DIR   media directory (default: <repo>/media)
  MEDIUM_HEADLESS    "1" headless (default), "0" to watch it work
  MEDIUM_CHANNEL     browser channel (default: chrome)
  MEDIUM_TIMEOUT_MS  per-step timeout (default: 60000)
"""
import hashlib
import os
import re
from html import escape

from .base import SyndicationError, Syndicator, SyndicationResult

try:
    from playwright.sync_api import sync_playwright

    _PW_OK = True
except Exception:  # pragma: no cover - Playwright missing
    _PW_OK = False

IMPORT_URL = "https://medium.com/p/import"
_DRAFT_URL = re.compile(r"/p/[0-9a-fA-F]+/edit")

# Medium sits behind Cloudflare, which 403s a plain headless launch.
_STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]
_STEALTH_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_STEALTH_JS = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"

_IMG_EXT = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "avif", "svg"}


def _cfg() -> dict:
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    state = os.environ.get("MEDIUM_STATE_FILE", "medium_auth.json").strip() or "medium_auth.json"
    if not os.path.isabs(state):
        state = os.path.join(repo, state)
    return {
        "base": os.environ.get("SITE_URL", "").strip().rstrip("/"),
        "state": state,
        "media": os.environ.get("MEDIUM_MEDIA_DIR", "").strip() or os.path.join(repo, "media"),
        "headless": os.environ.get("MEDIUM_HEADLESS", "1").strip() != "0",
        "channel": os.environ.get("MEDIUM_CHANNEL", "chrome").strip() or "chrome",
        "timeout": int(os.environ.get("MEDIUM_TIMEOUT_MS", "60000") or 60000),
    }


def _absolute(path: str, base: str) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return base + ("" if path.startswith("/") else "/") + path


def render_html(doc: dict, canonical_url: str, base: str) -> str:
    """A standalone article page for Medium's importer to fetch."""
    title = (doc or {}).get("title") or "Untitled"
    body = []
    for block in (doc or {}).get("blocks", []) or []:
        if block.get("type") == "text":
            for para in (block.get("content") or "").split("\n\n"):
                if para.strip():
                    body.append("<p>%s</p>" % escape(para.strip()))
        elif block.get("type") == "media":
            for path in block.get("media_paths") or []:
                ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
                src = escape(_absolute(path, base))
                if ext in _IMG_EXT:
                    body.append('<figure><img src="%s" alt=""></figure>' % src)
                elif ext in {"mp4", "webm", "mov", "mkv", "avi"}:
                    body.append('<figure><video controls src="%s"></video></figure>' % src)
                else:
                    body.append('<p><a href="%s">%s</a></p>' % (src, escape(path)))

    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<title>%s</title>" % escape(title),
        '<meta name="description" content="%s">' % escape(title),
        '<meta property="og:type" content="article">',
        '<meta property="og:title" content="%s">' % escape(title),
        '<meta property="og:description" content="%s">' % escape(title),
        '<meta property="og:url" content="%s">' % escape(canonical_url or ""),
        '<link rel="canonical" href="%s">' % escape(canonical_url or ""),
        "</head><body><article>",
        "<h1>%s</h1>" % escape(title),
        "\n".join(body),
        "</article>",
    ]
    if canonical_url:
        parts.append('<p><em>Originally published at <a href="%s">%s</a></em></p>'
                     % (escape(canonical_url), escape(canonical_url)))
    parts.append("</body></html>")
    return "\n".join(parts)


def write_page(doc: dict, canonical_url: str, post_id: str, cfg: dict) -> str | None:
    """Write the article page under media/ and return its PUBLIC url.

    Returns None when there is no public base: the importer fetches the URL from
    Medium's servers, so a localhost address is useless.
    """
    base = cfg["base"]
    if not base:
        return None
    os.makedirs(cfg["media"], exist_ok=True)
    seed = str(post_id or canonical_url or "article")
    filename = "medium_%s.html" % hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    with open(os.path.join(cfg["media"], filename), "w", encoding="utf-8") as fh:
        fh.write(render_html(doc, canonical_url, base))
    return "%s/media/%s" % (base, filename)


class MediumSyndicator(Syndicator):
    id = "medium"
    label = "Medium"

    def is_configured(self) -> bool:
        """Needs Playwright, a signed-in session, and a public base to serve from."""
        cfg = _cfg()
        return bool(_PW_OK and cfg["base"] and os.path.exists(cfg["state"]))

    def text_limit(self) -> int | None:
        """Medium accepts long stories, so it must not shrink other platforms."""
        return None

    def publish_detailed(self, text: str, url: str, media: list[str] | None = None,
                         doc: dict | None = None) -> SyndicationResult:
        if not _PW_OK:
            raise SyndicationError("Medium needs Playwright, which is not installed here.")
        if not doc:
            raise SyndicationError(
                "Medium publishes the article itself, so it needs the document - not just "
                "the shortened social text. It is article-only by design.")

        cfg = _cfg()
        if not cfg["base"]:
            raise SyndicationError(
                "Medium needs a public SITE_URL: its importer fetches the page from Medium's "
                "own servers, so localhost cannot work. Set SITE_URL to the public base that "
                "serves media/, then retry.")
        if not url:
            raise SyndicationError("Medium needs the article's canonical URL.")

        page_url = write_page(doc, url, (doc or {}).get("post_id", ""), cfg)
        if not page_url:
            raise SyndicationError("Could not write the article page under media/.")
        draft = self._import(page_url, cfg)
        return {"url": draft, "remote_id": _remote_id(draft)}

    def _import(self, page_url: str, cfg: dict) -> str:
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel=cfg["channel"], headless=cfg["headless"],
                                             args=_STEALTH_ARGS)
                try:
                    ctx = browser.new_context(storage_state=cfg["state"], user_agent=_STEALTH_UA,
                                              viewport={"width": 1280, "height": 900})
                    ctx.add_init_script(_STEALTH_JS)
                    page = ctx.new_page()
                    page.set_default_timeout(cfg["timeout"])
                    page.goto(IMPORT_URL, wait_until="domcontentloaded")
                    if "signin" in page.url:
                        raise SyndicationError(
                            "Medium is not signed in. Sign in once, then export the session: "
                            "playwright-cli -s=<session> state-save <state>.json")

                    field = page.wait_for_selector("div[contenteditable=true]", timeout=cfg["timeout"])
                    if field is None:
                        raise SyndicationError("Medium's import field never appeared.")
                    field.click()
                    page.evaluate(
                        "() => { const ed = document.querySelector('div[contenteditable=true]');"
                        " ed.focus(); const sel = window.getSelection();"
                        " const r = document.createRange(); r.selectNodeContents(ed);"
                        " sel.removeAllRanges(); sel.addRange(r);"
                        " document.execCommand('delete', false, null); }")
                    page.evaluate("(t) => document.execCommand('insertText', false, t)", page_url)

                    page.get_by_role("button", name="Import").click()
                    page.wait_for_url(_DRAFT_URL, timeout=cfg["timeout"])
                    return page.url.split("?")[0]
                finally:
                    browser.close()
        except SyndicationError:
            raise
        except Exception as e:
            raise SyndicationError("Medium import failed: %s: %s" % (type(e).__name__, str(e)[:200]))


def _remote_id(draft_url: str) -> str | None:
    m = re.search(r"/p/([0-9a-fA-F]+)/", draft_url or "")
    return m.group(1) if m else None
