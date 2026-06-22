"""Skill 3: AI image generation sized for a template placeholder.

Supports both OpenAI image model families and finds the one the account
actually has access to:

    gpt-image-1 / gpt-image-1-mini  (newer accounts)
    dall-e-3 / dall-e-2             (older accounts)

Each model only renders fixed sizes, so the nearest shape to the
placeholder's aspect ratio is requested and the result is center-cropped
with Pillow to match exactly — the picture drops into the template without
distortion. The first model that works is remembered for the rest of the
process, so fallback costs at most one failed call.
"""

from __future__ import annotations

import base64
import io
import re

from PIL import Image

from .config import get_client, IMAGE_MODEL
from .usage import tracker

_FALLBACK_MODELS = ["gpt-image-1", "gpt-image-1-mini", "dall-e-3", "dall-e-2"]

_MODEL_SIZES = {
    "dall-e-3":        {"1024x1024": 1.0, "1792x1024": 1.75, "1024x1792": 0.571},
    "gpt-image-1":     {"1024x1024": 1.0, "1536x1024": 1.5, "1024x1536": 0.667},
    "gpt-image-1-mini": {"1024x1024": 1.0, "1536x1024": 1.5, "1024x1536": 0.667},
    "dall-e-2":        {"1024x1024": 1.0},
}

# remembered across calls once a model succeeds
_working_model: str | None = None


def _build_kwargs(model: str, prompt: str, aspect_ratio: float,
                  quality: str, style: str) -> dict:
    sizes = _MODEL_SIZES.get(model, _MODEL_SIZES["gpt-image-1"])
    size = min(sizes, key=lambda s: abs(sizes[s] - aspect_ratio))
    kwargs = dict(model=model, prompt=prompt, size=size, n=1)
    if model.startswith("dall-e-3"):
        kwargs.update(quality=quality, style=style, response_format="b64_json")
    elif model.startswith("gpt-image"):
        kwargs["quality"] = {"standard": "medium", "hd": "high"}.get(
            quality, quality if quality in ("low", "medium", "high", "auto") else "medium")
    return kwargs


def _is_model_missing(exc: Exception) -> bool:
    msg = str(exc)
    return "does not exist" in msg or "'param': 'model'" in msg


def _call_with_param_stripping(client, kwargs: dict):
    """Call images.generate, removing any parameter the API rejects."""
    kwargs = dict(kwargs)
    while True:
        try:
            return client.images.generate(**kwargs), kwargs
        except Exception as exc:
            bad = re.search(r"[Pp]aram(?:eter)?'?:?\s*'(\w+)'", str(exc))
            if (bad and bad.group(1) in kwargs
                    and bad.group(1) not in ("model", "prompt")):
                kwargs.pop(bad.group(1))
                continue
            raise


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
    quality: str = "standard",   # "standard" | "hd" (mapped per model)
    style: str = "vivid",        # dall-e-3 only; ignored elsewhere
) -> bytes:
    """Render an image with whichever OpenAI image model the account has,
    and return PNG bytes cropped to aspect_ratio (width / height)."""
    client = get_client()

    if _working_model:
        candidates = [_working_model]
    else:
        candidates = [IMAGE_MODEL] + [m for m in _FALLBACK_MODELS if m != IMAGE_MODEL]

    last_exc: Exception | None = None
    for model in candidates:
        kwargs = _build_kwargs(model, prompt, aspect_ratio, quality, style)
        try:
            response, used_kwargs = _call_with_param_stripping(client, kwargs)
        except Exception as exc:
            if _is_model_missing(exc):
                last_exc = exc
                continue            # account lacks this model -> try next
            raise
        globals()["_working_model"] = model
        tracker.record_image(used_kwargs["size"],
                             used_kwargs.get("quality", "standard"),
                             usage=getattr(response, "usage", None))

        data = response.data[0]
        if getattr(data, "b64_json", None):
            raw = base64.b64decode(data.b64_json)
        else:  # URL response shape
            import httpx
            raw = httpx.get(data.url, timeout=60).content
        return _center_crop(raw, aspect_ratio)

    raise last_exc or RuntimeError("no usable image model found")
