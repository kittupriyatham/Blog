"""Render a "text card" so a text-only post can go to image-first platforms.

Instagram and Pinterest refuse a text-only post. Rather than force the author to
attach a picture, we shorten the post text, render it onto a gradient card, and
publish that card as the post's image.

YouTube is deliberately NOT covered here - it needs a real video, which cannot
be synthesised from text.

Pillow is optional: `available()` reports whether rendering is possible, so
callers can degrade to a clear error instead of crashing.
"""
import hashlib
import os
import textwrap

try:
    from PIL import Image, ImageDraw, ImageFont

    _PIL_OK = True
except Exception:  # pragma: no cover - Pillow missing
    _PIL_OK = False

# 1080x1080 is accepted by both Instagram (feed) and Pinterest.
CARD_W, CARD_H = 1080, 1080

# Gradient endpoints (brand indigo -> blue), matching the site palette.
_TOP = (79, 70, 229)
_BOTTOM = (37, 99, 235)

_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


def available() -> bool:
    """True when Pillow is importable, so a card can actually be rendered."""
    return _PIL_OK


def summarize(text: str, limit: int = 240) -> str:
    """Shorten `text` so it stays legible on a card.

    Prefers to stop at a sentence end, falling back to a word boundary, so the
    card never ends mid-word. This is deliberately extractive - no model call.
    """
    flat = " ".join((text or "").split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    for sep in (". ", "! ", "? "):
        i = cut.rfind(sep)
        if i > limit * 0.5:
            return cut[: i + 1].strip()
    i = cut.rfind(" ")
    return (cut[:i] if i > 0 else cut).strip() + "\u2026"


def _font(size: int):
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _gradient(width: int, height: int):
    img = Image.new("RGB", (width, height), _TOP)
    draw = ImageDraw.Draw(img)
    span = max(height - 1, 1)
    for y in range(height):
        t = y / span
        draw.line(
            [(0, y), (width, y)],
            fill=(
                int(_TOP[0] + (_BOTTOM[0] - _TOP[0]) * t),
                int(_TOP[1] + (_BOTTOM[1] - _TOP[1]) * t),
                int(_TOP[2] + (_BOTTOM[2] - _TOP[2]) * t),
            ),
        )
    return img


def render(text: str, out_path: str, width: int = CARD_W, height: int = CARD_H) -> str:
    """Write a card PNG containing a shortened `text`. Returns `out_path`."""
    if not _PIL_OK:
        raise RuntimeError("Pillow is not installed; cannot render a text card.")

    body = summarize(text)
    # Smaller type as the text grows, so long posts still fit without clipping.
    size = 64 if len(body) < 160 else (54 if len(body) < 260 else 44)
    font = _font(size)

    wrap_at = max(10, int(width / (size * 0.58)))
    lines = textwrap.wrap(body, width=wrap_at) or [""]
    line_h = int(size * 1.45)
    y = (height - len(lines) * line_h) // 2

    img = _gradient(width, height)
    draw = ImageDraw.Draw(img)
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (width - w) / 2
        # Soft drop shadow keeps white text readable over the lighter end.
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_h

    img.save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


def write(text: str, media_folder: str, post_id: str = "") -> str:
    """Render a card into `media_folder` and return its LOCAL path.

    Local is deliberate: the SocialAPI adapter uploads the file and publishes by
    `media_id`, so the platform never fetches anything and no public URL - host,
    tunnel or otherwise - is needed. That is what makes image-first platforms
    work from a local machine.
    """
    if not _PIL_OK:
        raise RuntimeError("Pillow is not installed; cannot render a text card.")

    os.makedirs(media_folder, exist_ok=True)

    # JPEG, not PNG: Meta rejects PNG feed images at container creation, and a
    # flat gradient card compresses well anyway.
    seed = str(post_id) if post_id else (text or "")
    filename = "textcard_%s.jpg" % hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    path = os.path.join(media_folder, filename)
    render(text, path)
    return path


def make(text: str, media_folder: str, public_base: str, post_id: str = "") -> str | None:
    """Deprecated URL-returning form.

    Superseded by `write()` plus a media-library upload: publishing by
    `media_id` needs no public URL, which is strictly better than serving the
    card over a host. Retained only so older callers keep working.
    """
    if not _PIL_OK or not public_base:
        return None
    path = write(text, media_folder, post_id)
    return "%s/media/%s" % (public_base.rstrip("/"), os.path.basename(path))
