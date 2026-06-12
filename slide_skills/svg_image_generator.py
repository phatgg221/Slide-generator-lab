"""Skill 13: cheap slide images — GPT-4o writes SVG, rasterized locally.

An image model charges ~$0.04-0.25 per picture; GPT-4o writing vector code
costs ~$0.01-0.02 and renders in seconds. The look is flat illustration /
diagram rather than photo — usually the right style for slides anyway.

    generate_svg_image(prompt, aspect_ratio)  -> PNG bytes
        (same contract as image_generator.generate_image, so the agent can
        swap sources)

Rasterizer: resvg-py, cairosvg, or svglib — whichever imports first.
"""

from __future__ import annotations

import io
import re

from PIL import Image

from .config import get_client, TEXT_MODEL
from .usage import tracker

_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.DOTALL | re.IGNORECASE)
_FORBIDDEN = re.compile(r"<\s*(script|foreignObject|image)\b", re.IGNORECASE)

_SYSTEM = """\
You are a vector artist for presentation slides. Produce ONE self-contained
SVG: an ABSTRACT GEOMETRIC composition that evokes the requested theme —
not a literal drawing of objects (literal objects render clumsy; abstraction
looks professional).

Think: overlapping translucent circles, flowing curves, layered arcs,
scattered dots, diagonal bands, concentric rings — arranged to suggest the
theme's mood and energy.

Rules:
- viewBox="0 0 {w} {h}" exactly; fill the whole canvas (background first).
- 12-25 shapes. Vary sizes dramatically (a few large anchors, many small
  accents). Use fill-opacity 0.3-0.8 on overlapping shapes for depth.
- 3-6 colors from one family plus an accent. Linear gradients allowed.
- Off-center, asymmetric composition with one clear focal area.
- No <text>, no <script>, no <image>, no external refs, no CSS classes —
  inline fill/stroke attributes only.
Return ONLY the SVG markup, nothing else.
"""


def _rasterize(svg: str, width_px: int) -> bytes:
    try:
        import resvg_py
        return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width_px))
    except ImportError:
        pass
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                                output_width=width_px)
    except (ImportError, OSError):
        pass
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    drawing = svg2rlg(io.StringIO(svg))
    scale = width_px / drawing.width
    drawing.width, drawing.height = width_px, drawing.height * scale
    drawing.scale(scale, scale)
    return renderPM.drawToString(drawing, fmt="PNG")


def generate_svg_markup(
    prompt: str,
    aspect_ratio: float = 1.0,
    *,
    palette: tuple[str, ...] | None = None,
    temperature: float = 0.8,
) -> str:
    """GPT-4o writes the SVG. Returns sanitized markup."""
    client = get_client()
    w = 1200
    h = round(w / aspect_ratio)
    user = f"Illustration request: {prompt}"
    if palette:
        user += f"\nUse this color palette: {', '.join('#' + c.lstrip('#') for c in palette)}"

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": _SYSTEM.format(w=w, h=h)},
            {"role": "user", "content": user},
        ],
    )
    tracker.record_chat(response.usage)

    match = _SVG_RE.search(response.choices[0].message.content)
    if not match:
        raise ValueError("GPT-4o returned no SVG markup")
    svg = match.group(0)
    if _FORBIDDEN.search(svg):
        svg = _FORBIDDEN.sub("<g hidden-", svg)  # neutralize, keep well-formed
    if "xmlns" not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def generate_svg_image(
    prompt: str,
    aspect_ratio: float = 1.0,
    *,
    width_px: int = 1200,
    palette: tuple[str, ...] | None = None,
    quality: str = "standard",   # accepted for interface parity; unused
    style: str = "vivid",        # accepted for interface parity; unused
) -> bytes:
    """Same contract as generate_image: prompt + aspect -> PNG bytes."""
    svg = generate_svg_markup(prompt, aspect_ratio, palette=palette)
    png = _rasterize(svg, width_px)

    # enforce exact aspect (the SVG should already match, but be safe)
    img = Image.open(io.BytesIO(png))
    current = img.width / img.height
    if abs(current - aspect_ratio) > 0.02:
        if current > aspect_ratio:
            new_w = int(img.height * aspect_ratio)
            x0 = (img.width - new_w) // 2
            img = img.crop((x0, 0, x0 + new_w, img.height))
        else:
            new_h = int(img.width / aspect_ratio)
            y0 = (img.height - new_h) // 2
            img = img.crop((0, y0, img.width, y0 + new_h))
    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()
