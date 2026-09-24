"""Prepare an attached image before it is uploaded for publishing.

Uploads go through a proxy with a request-size ceiling well below the 50 MB the
upload API advertises: a 6.37 MB PNG comes back as nginx `413 Request Entity Too
Large`. Downscaling and re-encoding keeps every upload small, and re-encoding to
JPEG also satisfies Meta, which rejects PNG feed images.

This runs for every image, on every platform. Gating it per platform meant the
untouched original was uploaded elsewhere and 413'd.

Video and other non-image attachments are returned unchanged.
"""
import math
import os
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow is a declared dependency
    Image = None  # type: ignore[assignment]

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}

# Comfortably under the upload ceiling, and plenty for a social image.
MAX_EDGE = 1600
MAX_BYTES = 1_500_000

# Instagram rejects anything outside 4:5 (0.8) to 1.91:1 (1.91).
INSTAGRAM_ASPECT = (0.8, 1.91)


def is_image(path):
    return os.path.splitext(path or "")[1].lower() in IMAGE_EXTS


def is_jpeg(path):
    """True when the file already is a JPEG, decided by magic bytes not extension."""
    try:
        with open(path, "rb") as fh:
            return fh.read(3) == b"\xff\xd8\xff"
    except OSError:
        return False


def _flatten(img):
    """Drop alpha onto white so a transparent PNG does not become a black block."""
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        return flat
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _ratio(size):
    w, h = size
    return float(w) / float(h) if h else 0.0


def _in_bounds(size, bounds):
    return bounds[0] <= _ratio(size) <= bounds[1]


def _fit_aspect(img, bounds):
    """Pad `img` until its width:height ratio sits inside `bounds`.

    Padding rather than cropping keeps the whole attachment - a very wide image
    gains bars instead of losing its edges. Instagram is the platform that needs
    this; it rejects an out-of-range ratio outright.

    Rounds up when adding height: flooring lands on the bound and a later resize
    can round the other way, pushing the ratio back out (1600x837 = 1.912 > 1.91).
    """
    low, high = bounds
    w, h = img.size
    ratio = _ratio(img.size)
    if low <= ratio <= high:
        return img

    if ratio > high:            # too wide -> add height
        target_h = int(math.ceil(w / high)) + 1
        canvas = Image.new("RGB", (w, target_h), (0, 0, 0))
        canvas.paste(img, (0, (target_h - h) // 2))
        return canvas
    target_w = int(math.ceil(h * low)) + 1   # too tall -> add width
    canvas = Image.new("RGB", (target_w, h), (0, 0, 0))
    canvas.paste(img, ((target_w - w) // 2, 0))
    return canvas


def _enforce_aspect(path, bounds):
    """Re-pad a saved file if resizing nudged it back outside `bounds`."""
    with Image.open(path) as im:
        if _in_bounds(im.size, bounds):
            return
        fixed = _fit_aspect(im.convert("RGB"), bounds)
        fixed.save(path, "JPEG", quality=88, optimize=True)


def _save(img, out):
    """Save as JPEG, shrinking until it fits MAX_BYTES."""
    edge = MAX_EDGE
    for _ in range(5):
        candidate: Any = img
        longest = max(img.size)
        if longest > edge:
            scale = float(edge) / float(longest)
            candidate = img.resize((max(1, round(img.size[0] * scale)),
                                    max(1, round(img.size[1] * scale))),
                                   Image.Resampling.LANCZOS)
        for quality in (90, 82, 72, 60):
            candidate.save(out, "JPEG", quality=quality, optimize=True)
            if os.path.getsize(out) <= MAX_BYTES:
                return True
        edge = int(edge * 0.75)
    return os.path.getsize(out) <= MAX_BYTES


def prepare_image(path, aspect=None):
    """Return a publishable version of `path`.

    Non-images, unreadable files and anything Pillow cannot handle come back
    unchanged, so this is safe to call on any attachment. The result is cached
    beside the original and reused on later publishes.
    """
    if Image is None or not is_image(path) or not os.path.isfile(path):
        return path

    suffix = "_ig" if aspect else ""
    out = os.path.join(os.path.dirname(path),
                       os.path.splitext(os.path.basename(path))[0] + suffix + ".jpg")
    try:
        if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(path):
            return out
        # All image work stays inside the `with`: _flatten returns the opened
        # object unchanged when the file is already RGB, and that object is
        # unusable once the context closes (paste/resize assert on a dead file).
        with Image.open(path) as opened:
            img = _flatten(opened)
            if aspect:
                img = _fit_aspect(img, aspect)
            _save(img, out)
        if aspect:
            _enforce_aspect(out, aspect)
    except Exception as e:
        # Never block a publish on image processing - send the original and let
        # the platform report it if it genuinely cannot be used.
        print("[imageprep] could not prepare %s: %s: %s"
              % (os.path.basename(path), type(e).__name__, e))
        return path
    return out
