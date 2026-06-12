"""Skill 3: DALL-E image generation sized for a template placeholder.

DALL-E 3 only renders 1024x1024, 1792x1024, or 1024x1792, so this picks the
nearest shape to the placeholder's aspect ratio, then center-crops with
Pillow to match it exactly — the picture drops into the template without
distortion.
"""

from __future__ import annotations

import base64
import io

from PIL import Image

from .config import get_client, IMAGE_MODEL
from .usage import tracker

_DALLE_SIZES = {
    "1024x1024": 1.0,
    "1792x1024": 1.75,
    "1024x1792": 0.571,
}


def _nearest_size(aspect_ratio: float) -> str:
    return min(_DALLE_SIZES, key=lambda s: abs(_DALLE_SIZES[s] - aspect_ratio))


def _center_crop(image_bytes: bytes, aspect_ratio: float) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    current = w / h
    if abs(current - aspect_ratio) > 0.01:
        if current > aspect_ratio:   # too wide -> trim sides
            new_w = int(h * aspect_ratio)
            x0 = (w - new_w) // 2
            img = img.crop((x0, 0, x0 + new_w, h))
        else:                        # too tall -> trim top/bottom
            new_h = int(w / aspect_ratio)
            y0 = (h - new_h) // 2
            img = img.crop((0, y0, w, y0 + new_h))
    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()


def generate_image(
    prompt: str,
    aspect_ratio: float = 1.0,
    *,
    quality: str = "standard",   # "standard" | "hd"
    style: str = "vivid",        # "vivid" | "natural"
) -> bytes:
    """Render an image with DALL-E and return PNG bytes cropped to
    aspect_ratio (width / height)."""
    client = get_client()
    size = _nearest_size(aspect_ratio)

    kwargs = dict(model=IMAGE_MODEL, prompt=prompt, size=size, n=1)
    if IMAGE_MODEL.startswith("dall-e"):
        kwargs.update(quality=quality, style=style, response_format="b64_json")
    try:
        response = client.images.generate(**kwargs)
    except Exception as exc:
        # Newer OpenAI API versions reject response_format (images are
        # returned base64 by default) — retry without it.
        if "response_format" in str(exc) and "response_format" in kwargs:
            kwargs.pop("response_format")
            response = client.images.generate(**kwargs)
        else:
            raise
    tracker.record_image(size, quality)

    data = response.data[0]
    if getattr(data, "b64_json", None):
        raw = base64.b64decode(data.b64_json)
    else:  # URL response shape
        import httpx
        raw = httpx.get(data.url, timeout=60).content
    return _center_crop(raw, aspect_ratio)
