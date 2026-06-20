"""Skill 17: build a self-contained animated HTML presentation.

Takes filled SVG slides (strings) and produces ONE deck.html with no
external dependencies: inlined SVGs (crisp vectors, selectable text),
keyboard/click/swipe navigation, fullscreen, and staggered CSS entrance
animations on each slide's elements — the part .pptx can never deliver
from Canva-style designs.

Embed on a website with <iframe src="deck.html"> or serve from FastAPI.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Union

ANIMATIONS = {
    "rise":  "opacity:0; transform:translateY(26px);",
    "fade":  "opacity:0;",
    "scale": "opacity:0; transform:scale(0.92);",
    "none":  "",
}

_MAX_STAGGERED = 40
_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)


_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  html, body {{ margin:0; height:100%; background:#111; overflow:hidden;
                font-family: Helvetica, Arial, sans-serif; }}
  .stage {{ position:relative; width:100vw; height:100vh; }}
  .slide {{ position:absolute; inset:0; display:flex; align-items:center;
            justify-content:center; opacity:0; visibility:hidden;
            transition:opacity .45s ease; }}
  .slide.active {{ opacity:1; visibility:visible; }}
  .slide svg {{ width:min(100vw, calc(100vh * {aspect})); height:auto;
                max-height:100vh; box-shadow:0 8px 40px rgba(0,0,0,.5);
                background:#fff; }}
  {anim_css}
  .hud {{ position:fixed; bottom:14px; right:18px; color:#aaa; z-index:10;
          font-size:14px; user-select:none; display:flex; gap:14px;
          align-items:center; }}
  .hud button {{ background:none; border:1px solid #555; color:#aaa;
                 border-radius:6px; padding:3px 10px; cursor:pointer;
                 font-size:13px; }}
  .hud button:hover {{ color:#fff; border-color:#999; }}
  .nav {{ position:fixed; top:0; bottom:0; width:18vw; z-index:5;
          cursor:pointer; }}
  .nav.prev {{ left:0; }} .nav.next {{ right:0; }}
</style>
</head>
<body>
<div class="stage">
{slides}
</div>
<div class="nav prev" onclick="step(-1)"></div>
<div class="nav next" onclick="step(1)"></div>
<div class="hud">
  <span id="counter"></span>
  <button onclick="toggleFull()">⛶</button>
</div>
<script>
  const slides = [...document.querySelectorAll('.slide')];
  let i = 0;
  function show(n) {{
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach((s, k) => {{
      s.classList.remove('active');
      if (k === i) {{
        void s.offsetWidth;            // restart entrance animations
        s.classList.add('active');
      }}
    }});
    document.getElementById('counter').textContent = (i + 1) + ' / ' + slides.length;
  }}
  function step(d) {{ show(i + d); }}
  function toggleFull() {{
    document.fullscreenElement ? document.exitFullscreen()
                               : document.documentElement.requestFullscreen();
  }}
  addEventListener('keydown', e => {{
    if (['ArrowRight', 'PageDown', ' '].includes(e.key)) step(1);
    if (['ArrowLeft', 'PageUp'].includes(e.key)) step(-1);
    if (e.key === 'f') toggleFull();
  }});
  let x0 = null;
  addEventListener('touchstart', e => x0 = e.touches[0].clientX);
  addEventListener('touchend', e => {{
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) step(dx < 0 ? 1 : -1);
    x0 = null;
  }});
  show(0);
</script>
</body>
</html>
"""


def _animation_css(animation: str, stagger_s: float, duration_s: float) -> str:
    """Entrance animation that never breaks SVG layout.

    CSS `transform` on an SVG child OVERRIDES that element's own
    `transform="translate(...)"` attribute, which silently relocates any
    positioned group to the origin. So the rise/scale motion is applied to the
    whole <svg> (a normal flex item — safe), and the per-element stagger uses
    OPACITY ONLY, which can never disturb positioning."""
    if animation not in ANIMATIONS:
        raise ValueError(f"Unknown animation {animation!r}. Available: {sorted(ANIMATIONS)}")
    if animation == "none":
        return ""
    svg_hidden = ANIMATIONS[animation]      # rise/scale/fade applied to the whole SVG
    rules = [
        f".slide svg {{ {svg_hidden} }}",
        f".slide.active svg {{ animation: deckenter {duration_s}s ease-out forwards; }}",
        "@keyframes deckenter { to { opacity:1; transform:none; } }",
        # per-element stagger — opacity only, never transform
        ".slide svg > * { opacity:0; }",
        f".slide.active svg > * {{ animation: elenter {duration_s}s ease-out forwards; }}",
        "@keyframes elenter { to { opacity:1; } }",
    ]
    for n in range(1, _MAX_STAGGERED + 1):
        rules.append(
            f".slide.active svg > *:nth-child({n}) "
            f"{{ animation-delay: {((n - 1) * stagger_s):.2f}s; }}")
    return "\n  ".join(rules)


_ID_DEF_RE = re.compile(r'\bid\s*=\s*"([^"]+)"')
_ID_URL_RE = re.compile(r'url\(\s*#([^)\s]+)\s*\)')
_ID_HREF_RE = re.compile(r'((?:xlink:)?href)\s*=\s*"#([^"]+)"')


def _namespace_ids(svg: str, i: int) -> str:
    """Prefix every element id (and its references) with the slide index, so
    inlining many SVGs into one page can't collide on shared ids — clipPaths,
    gradients, masks, filters. Fragment refs only; data: URIs are untouched."""
    p = f"s{i}_"
    svg = _ID_DEF_RE.sub(lambda m: f'id="{p}{m.group(1)}"', svg)
    svg = _ID_URL_RE.sub(lambda m: f'url(#{p}{m.group(1)})', svg)
    svg = _ID_HREF_RE.sub(lambda m: f'{m.group(1)}="#{p}{m.group(2)}"', svg)
    return svg


def build_html_deck(
    svgs: list[str],
    output_path: Union[str, Path],
    *,
    title: str = "Presentation",
    animation: str = "rise",
    stagger_s: float = 0.10,
    duration_s: float = 0.6,
    aspect: float = 1440 / 810,
) -> Path:
    """Write the self-contained presentation HTML and return its path."""
    sections = []
    for i, svg in enumerate(svgs):
        if not _SVG_OPEN_RE.search(svg):
            raise ValueError(f"slide {i} is not an SVG")
        svg = _namespace_ids(svg, i)
        sections.append(f'<section class="slide" data-i="{i}">{svg}</section>')

    page = _PAGE.format(
        title=html.escape(title),
        aspect=f"{aspect:.4f}",
        anim_css=_animation_css(animation, stagger_s, duration_s),
        slides="\n".join(sections),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    return output_path
