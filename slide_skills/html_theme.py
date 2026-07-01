"""Skill: native HTML/CSS slide themes (Gamma-style web decks).

Unlike extract_template_smart (which paints text over a flattened raster of a
Canva slide), this renders each slide as real HTML in a CSS grid/flex layout.
Text reflows, never overlaps, and stays vector-crisp at any zoom — the look is
driven by a small design-token system (palette + fonts + type scale) plus a
curated set of layouts (title, section, bullets, stats, quote, comparison,
feature, closing).

Pipeline (mirrors document_deck):
    document -> map to (layout + fields) plan -> optional AI images
             -> render each layout -> assemble one self-contained deck.html

Entry point: generate_html_deck_from_document(doc, output_path, theme="auto").
"""

from __future__ import annotations

import base64
import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Union

from .config import TEXT_MODEL, get_client
from .document_deck import parse_document
from .usage import tracker

# ---------------------------------------------------------------------------
# 1. Theme tokens
# ---------------------------------------------------------------------------


@dataclass
class Theme:
    name: str
    bg: str
    ink: str
    muted: str
    accent: str
    rule: str
    panel_a: str          # image-panel gradient (light end)
    panel_b: str          # image-panel gradient (dark end)
    serif: str = '"Fraunces", Georgia, "Times New Roman", serif'
    sans: str = '"Inter", -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'

    def css_vars(self) -> str:
        return (
            f"--bg:{self.bg};--ink:{self.ink};--muted:{self.muted};"
            f"--accent:{self.accent};--rule:{self.rule};"
            f"--panel-a:{self.panel_a};--panel-b:{self.panel_b};"
            f"--serif:{self.serif};--sans:{self.sans};"
        )


THEMES: dict[str, Theme] = {
    "editorial-warm": Theme("editorial-warm", "#FBEBCF", "#4A0E1B", "#8a5a4a",
                            "#8B1E2D", "#d8b48c", "#7d0f22", "#2a0910"),
    "midnight": Theme("midnight", "#0E1116", "#EAF0F7", "#9fb0c3",
                      "#5B9BFF", "#2a3543", "#1c3a6e", "#0a1526"),
    "clean-slate": Theme("clean-slate", "#FFFFFF", "#12161C", "#5c6672",
                         "#2F6BFF", "#e3e8ef", "#2F6BFF", "#0a1a3a"),
    "forest": Theme("forest", "#F3F1E7", "#1E2B21", "#5a6b5c",
                    "#2E7D5B", "#cdd6c4", "#1f6b4a", "#0c2418"),
    "sunset": Theme("sunset", "#FFF3EC", "#3A1A1F", "#8a5f56",
                    "#E4572E", "#f0c9b4", "#e0552d", "#5a1e12"),
}


def propose_theme(brief: str, *, language: str | None = None) -> Theme:
    """Ask the model which built-in theme best fits the deck's subject/mood, or
    to invent a cohesive custom palette. Falls back to editorial-warm."""
    names = ", ".join(THEMES)
    sys = (
        "You are a presentation art director. Given a deck brief, choose the "
        f"single best-fitting theme from this list: {names}. If none fit the "
        "subject's mood, invent a cohesive, high-contrast custom palette "
        "instead. Return ONLY JSON: either {\"theme\":\"<name>\"} or "
        "{\"custom\":{\"bg\":\"#..\",\"ink\":\"#..\",\"muted\":\"#..\","
        "\"accent\":\"#..\",\"rule\":\"#..\",\"panel_a\":\"#..\",\"panel_b\":\"#..\"}}. "
        "bg must be light-or-dark enough that ink text is clearly readable; "
        "accent is a vivid brand color; panel_a/panel_b make a rich gradient."
    )
    try:
        client = get_client()
        r = client.chat.completions.create(
            model=TEXT_MODEL, temperature=0.4,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys},
                      {"role": "user", "content": brief[:2000]}],
        )
        tracker.record_chat(r.usage)
        data = json.loads(r.choices[0].message.content)
    except Exception:
        return THEMES["editorial-warm"]

    if data.get("theme") in THEMES:
        return THEMES[data["theme"]]
    c = data.get("custom") or {}
    try:
        return Theme("custom", c["bg"], c["ink"], c["muted"], c["accent"],
                     c["rule"], c["panel_a"], c["panel_b"])
    except KeyError:
        return THEMES["editorial-warm"]


def resolve_theme(theme: Union[str, Theme, None], brief: str) -> Theme:
    if isinstance(theme, Theme):
        return theme
    if theme in THEMES:
        return THEMES[theme]
    if theme in (None, "auto"):
        return propose_theme(brief)
    return THEMES["editorial-warm"]


# ---------------------------------------------------------------------------
# 2. Layouts — each renders a slide's inner HTML from a flat fields dict
# ---------------------------------------------------------------------------

def _esc(v) -> str:
    return html.escape(str(v or "")).replace("\n", "<br>")


def _panel(theme: Theme, img_uri: str | None) -> str:
    """The decorative side/feature panel: an AI image if supplied, else a
    themed gradient."""
    if img_uri:
        return (f'<div class="panel" style="background-image:'
                f'url({img_uri});background-size:cover;background-position:center"></div>')
    return '<div class="panel"></div>'


def _items(field_val, tag_open="<li>", tag_close="</li>") -> str:
    if not field_val:
        return ""
    out = []
    for it in field_val:
        if isinstance(it, dict):
            it = it.get("text") or it.get("title") or it.get("point") or ""
        out.append(f"{tag_open}{_esc(it)}{tag_close}")
    return "".join(out)


def render_title(f, theme, img):
    kick = f"<span class=\"kicker\">{_esc(f['kicker'])}</span>" if f.get("kicker") else ""
    sub = f"<p>{_esc(f['subtitle'])}</p>" if f.get("subtitle") else ""
    label = _esc(f.get("label") or f.get("brand") or "")
    lbl = f'<div class="rise"><div class="label">{label}</div><hr class="hr"></div>' if label else ""
    return (
        f'<div class="l-title">{_panel(theme, img)}'
        f'<div class="body">'
        f'<div class="rise">{kick}</div>{lbl}'
        f'<h1 class="rise">{_esc(f.get("title"))}</h1>'
        f'<div class="rise">{sub}</div>'
        f'</div></div>'
    )


def render_section(f, theme, img):
    num = _esc(f.get("number") or "")
    numhtml = f'<div class="secnum rise">{num}</div>' if num else ""
    sub = f'<p class="rise">{_esc(f["subtitle"])}</p>' if f.get("subtitle") else ""
    return (
        f'<div class="pad l-section">{numhtml}'
        f'<h2 class="rise">{_esc(f.get("title"))}</h2>{sub}</div>'
    )


def render_bullets(f, theme, img):
    kick = f'<span class="kicker rise">{_esc(f["kicker"])}</span>' if f.get("kicker") else ""
    items = f.get("bullets") or f.get("items") or []
    rows = []
    for n, it in enumerate(items, 1):
        if isinstance(it, dict):
            it = it.get("text") or it.get("title") or ""
        rows.append(f'<li><span class="n">{n:02d}</span><span>{_esc(it)}</span></li>')
    return (
        f'<div class="pad">{kick}'
        f'<h2 class="rise">{_esc(f.get("title"))}</h2>'
        f'<ul class="list rise">{"".join(rows)}</ul></div>'
    )


def render_stats(f, theme, img):
    kick = f'<span class="kicker rise">{_esc(f["kicker"])}</span>' if f.get("kicker") else ""
    stats = f.get("stats") or []
    cells = []
    for s in stats:                       # no cap — grid reflows to any count
        val = s.get("value") if isinstance(s, dict) else s
        cap = s.get("caption") if isinstance(s, dict) else ""
        cells.append(f'<div class="stat"><div class="big">{_esc(val)}</div>'
                     f'<div class="cap">{_esc(cap)}</div></div>')
    # aim for ~3 per row; the grid auto-wraps extra items onto new rows
    per_row = 2 if len(cells) <= 2 else (2 if len(cells) == 4 else 3)
    grid = (f'<div class="stats rise" '
            f'style="grid-template-columns:repeat({per_row},1fr)">{"".join(cells)}</div>')
    return (
        f'<div class="pad">{kick}'
        f'<h2 class="rise">{_esc(f.get("title"))}</h2>{grid}</div>'
    )


def render_quote(f, theme, img):
    who = f'<div class="who rise">— {_esc(f["author"])}</div>' if f.get("author") else ""
    return (
        f'<div class="pad l-quote"><div class="mark rise">&ldquo;</div>'
        f'<blockquote class="rise">{_esc(f.get("quote") or f.get("title"))}</blockquote>{who}</div>'
    )


def render_comparison(f, theme, img):
    kick = f'<span class="kicker rise">{_esc(f["kicker"])}</span>' if f.get("kicker") else ""
    left = f.get("left") or {}
    right = f.get("right") or {}

    def col(c):
        return (f'<div class="col"><h3>{_esc(c.get("heading"))}</h3>'
                f'<ul>{_items(c.get("points") or c.get("bullets"))}</ul></div>')
    return (
        f'<div class="pad">{kick}<h2 class="rise">{_esc(f.get("title"))}</h2>'
        f'<div class="cols rise">{col(left)}<div class="vs">vs</div>{col(right)}</div></div>'
    )


def render_feature(f, theme, img):
    kick = f'<span class="kicker">{_esc(f["kicker"])}</span>' if f.get("kicker") else ""
    body = f'<p>{_esc(f["body"])}</p>' if f.get("body") else ""
    chips = ""
    if f.get("bullets"):
        chips = ('<div class="rise">'
                 + _items(f.get("bullets"), '<span class="chip">', "</span>")
                 + "</div>")
    return (
        f'<div class="l-feature">'
        f'<div class="body"><div class="rise">{kick}</div>'
        f'<h2 class="rise">{_esc(f.get("title"))}</h2>'
        f'<div class="rise">{body}</div>{chips}'
        f'</div>{_panel(theme, img)}</div>'
    )


def render_closing(f, theme, img):
    kick = f'<span class="kicker rise">{_esc(f["kicker"])}</span>' if f.get("kicker") else ""
    sub = f'<p class="rise">{_esc(f["subtitle"])}</p>' if f.get("subtitle") else ""
    contact = f'<div class="contact rise">{_esc(f["contact"])}</div>' if f.get("contact") else ""
    return (
        f'<div class="pad l-closing">{kick}'
        f'<h1 class="rise">{_esc(f.get("title"))}</h1>{sub}{contact}</div>'
    )


@dataclass
class Layout:
    name: str
    description: str
    fields: str                         # human description of expected fields
    render: Callable
    needs_image: bool = False


LAYOUTS: dict[str, Layout] = {
    "title": Layout("title", "Opening/cover slide with a big headline and an image panel.",
                    "kicker (short eyebrow), label (brand/name), title (headline), subtitle (1-2 sentences)",
                    render_title, needs_image=True),
    "agenda": Layout("agenda", "An outline listing the deck's sections.",
                     "kicker, title, bullets (list of section names)", render_bullets),
    "section": Layout("section", "A divider announcing a new part; big and minimal.",
                      "number (e.g. '01'), title, subtitle (optional)", render_section),
    "bullets": Layout("bullets", "A list of points, steps, or takeaways.",
                      "kicker, title, bullets (list of short strings)", render_bullets),
    "stats": Layout("stats", "2-4 big headline numbers with captions. ONLY when real figures exist.",
                    "kicker, title, stats (list of {value, caption})", render_stats),
    "quote": Layout("quote", "A single powerful testimonial or quote on a dark background.",
                    "quote (the sentence), author", render_quote),
    "comparison": Layout("comparison", "Two things side by side (us vs them, before/after).",
                         "kicker, title, left {heading, points[]}, right {heading, points[]}", render_comparison),
    "feature": Layout("feature", "One concept explained with supporting text and an image panel.",
                      "kicker, title, body (paragraph), bullets (optional), and an image", render_feature, needs_image=True),
    "closing": Layout("closing", "Closing / call-to-action / contact slide.",
                      "kicker, title, subtitle, contact (email/site)", render_closing),
}


# ---------------------------------------------------------------------------
# 3. Map document -> (layout + fields) plan
# ---------------------------------------------------------------------------

def _map_system() -> str:
    catalog = "\n".join(f'- "{l.name}": {l.description} Fields: {l.fields}'
                        for l in LAYOUTS.values())
    return (
        "You design a beautiful, editorial slide deck from a document outline. "
        "For EACH document section, pick the best layout and write its fields.\n\n"
        f"Available layouts:\n{catalog}\n\n"
        "Rules:\n"
        "- Create ONE slide per section, in order. Use the opening for a 'title' "
        "slide and the closing for a 'closing' slide.\n"
        "- Add a 'agenda' slide only if a section is clearly an outline/overview.\n"
        "- Use 'stats' ONLY when the section has 2+ concrete numbers; put the "
        "figure in value (e.g. '$2.4B', '32%') and a short label in caption.\n"
        "- Keep text tight and specific: headlines under ~8 words, bullets under "
        "~12 words, subtitles 1-2 sentences. Never invent facts.\n"
        "- 'kicker' is a 1-3 word eyebrow label (e.g. 'How it works').\n"
        "- Prefer variety across layouts; don't repeat the same layout back-to-back "
        "unless the content demands it.\n\n"
        'Return ONLY JSON: {"slides":[{"layout":"<name>","fields":{...}}]}'
    )


def map_document_to_html_plan(sections, *, language=None, research_summary=""):
    doc_view = [{"heading": s["heading"], "text": s["text"][:1200],
                 "has_bullets": bool(s["bullets"]), "has_quote": bool(s["quotes"]),
                 "has_numbers": s["has_numbers"]} for s in sections]
    user = f"Document sections (in order):\n{json.dumps(doc_view, ensure_ascii=False)}"
    if research_summary:
        user += f"\n\nResearch findings (make points specific):\n{research_summary[:3000]}"
    if language:
        user += f"\n\nWrite all content in {language}."

    client = get_client()
    r = client.chat.completions.create(
        model=TEXT_MODEL, temperature=0.5,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _map_system()},
                  {"role": "user", "content": user}],
    )
    tracker.record_chat(r.usage)
    plan = json.loads(r.choices[0].message.content)
    slides = [s for s in plan.get("slides", [])
              if isinstance(s, dict) and s.get("layout") in LAYOUTS]
    return slides


# ---------------------------------------------------------------------------
# 4. Images (optional) for image-bearing layouts
# ---------------------------------------------------------------------------

def _image_uri_for(fields: dict, layout: Layout) -> str | None:
    from .image_generator import generate_image
    subject = fields.get("title") or fields.get("kicker") or ""
    extra = fields.get("subtitle") or fields.get("body") or ""
    prompt = (
        f"An elegant, abstract, editorial illustration evoking: {subject}. "
        f"{extra}. Rich color, soft depth, premium magazine aesthetic. "
        f"No text, no words, no letters, no charts."
    )
    ar = 0.72 if layout.name == "title" else 1.15
    png = generate_image(prompt, aspect_ratio=ar)
    return "data:image/png;base64," + base64.b64encode(png).decode()


# ---------------------------------------------------------------------------
# 5. CSS + assembly
# ---------------------------------------------------------------------------

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0b0b0d;font-family:var(--sans);color:var(--ink)}
.stage{height:100vh;display:flex;align-items:center;justify-content:center}
.slide{position:absolute;width:min(96vw,1180px);aspect-ratio:16/9;background:var(--bg);
  color:var(--ink);border-radius:14px;overflow:hidden;box-shadow:0 30px 90px rgba(0,0,0,.55);
  opacity:0;transform:translateY(18px) scale(.985);pointer-events:none;
  transition:opacity .5s ease,transform .5s ease}
.slide.active{opacity:1;transform:none;pointer-events:auto}
.slide.active .rise{animation:rise .6s cubic-bezier(.2,.7,.2,1) both}
.slide.active .rise:nth-child(2){animation-delay:.07s}
.slide.active .rise:nth-child(3){animation-delay:.14s}
.slide.active .rise:nth-child(4){animation-delay:.21s}
.slide.active .rise:nth-child(5){animation-delay:.28s}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.kicker{font-size:.78rem;text-transform:uppercase;letter-spacing:.22em;color:var(--accent);font-weight:700}
.label{font-family:var(--serif);font-size:1.35rem}
.hr{height:1px;background:var(--rule);border:0;margin:.9rem 0 0}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(2.4rem,4.6vw,4.2rem);line-height:1.04;letter-spacing:-.01em}
h2{font-family:var(--serif);font-weight:600;font-size:clamp(1.9rem,3.4vw,3rem);line-height:1.08}
h3{font-family:var(--serif);font-weight:600;font-size:1.4rem;margin-bottom:.7rem}
p{font-size:clamp(1rem,1.4vw,1.18rem);line-height:1.6;color:var(--muted);max-width:46ch}
.pad{padding:clamp(2.2rem,6vw,4.6rem);height:100%;display:flex;flex-direction:column;justify-content:center}
/* title & feature: split panel + text */
.l-title,.l-feature{display:grid;height:100%}
.l-title{grid-template-columns:38% 1fr}
.l-feature{grid-template-columns:1fr 42%}
.panel{background:radial-gradient(120% 90% at 30% 20%,color-mix(in srgb,var(--accent) 70%,transparent),transparent 60%),
  radial-gradient(90% 90% at 70% 80%,var(--panel-b),transparent 55%),
  linear-gradient(160deg,var(--panel-a),var(--panel-b));position:relative}
.panel::after{content:"";position:absolute;inset:0;
  background:linear-gradient(115deg,rgba(255,255,255,.16),transparent 40%);mix-blend-mode:screen}
.l-title .body,.l-feature .body{padding:0 clamp(2rem,5vw,4.4rem);display:flex;flex-direction:column;justify-content:center;gap:1.3rem}
.l-title h1{border-left:4px solid var(--accent);padding-left:1.1rem}
/* section divider */
.l-section{justify-content:center}
.secnum{font-family:var(--serif);font-size:clamp(3rem,8vw,6rem);color:var(--accent);line-height:.9;opacity:.85;margin-bottom:.4rem}
/* bullets */
.list{list-style:none;margin-top:2rem;display:flex;flex-direction:column;gap:1.05rem;max-width:60ch}
.list li{display:flex;gap:1rem;align-items:flex-start;font-size:clamp(1.05rem,1.6vw,1.3rem);line-height:1.45}
.list .n{font-family:var(--serif);color:var(--accent);min-width:2.2rem;font-weight:700}
/* stats */
.stats{display:grid;gap:2.2rem;margin-top:2.4rem}
.stat .big{font-family:var(--serif);font-size:clamp(2.6rem,5vw,4rem);color:var(--accent);line-height:1}
.stat .cap{margin-top:.5rem;color:var(--muted);font-size:1.02rem}
/* quote */
.l-quote{background:var(--ink);color:var(--bg)}
.l-quote .mark{font-family:var(--serif);font-size:6rem;color:var(--accent);line-height:.6}
.l-quote blockquote{font-family:var(--serif);font-size:clamp(1.7rem,3.4vw,2.5rem);line-height:1.3;max-width:24ch;margin-top:1rem}
.l-quote .who{margin-top:1.8rem;letter-spacing:.15em;text-transform:uppercase;font-size:.8rem;color:var(--rule)}
/* comparison */
.cols{display:grid;grid-template-columns:1fr auto 1fr;gap:1.6rem;align-items:start;margin-top:2rem}
.cols .col ul{list-style:none;display:flex;flex-direction:column;gap:.7rem}
.cols .col li{font-size:1.08rem;line-height:1.4;padding-left:1rem;position:relative;color:var(--muted)}
.cols .col li::before{content:"";position:absolute;left:0;top:.6em;width:6px;height:6px;border-radius:50%;background:var(--accent)}
.cols .vs{font-family:var(--serif);color:var(--accent);align-self:center;font-size:1.2rem}
/* feature chips */
.chip{display:inline-block;background:color-mix(in srgb,var(--accent) 14%,transparent);
  color:var(--ink);border:1px solid var(--rule);border-radius:999px;padding:.3rem .9rem;margin:.3rem .4rem 0 0;font-size:.95rem}
/* closing */
.l-closing{justify-content:center}
.contact{margin-top:1.6rem;font-family:var(--serif);font-size:1.3rem;color:var(--accent)}
.nav{position:fixed;bottom:18px;right:22px;color:#bbb;font:13px var(--sans);display:flex;gap:12px;align-items:center;z-index:20}
.nav button{background:#1c1c22;color:#ddd;border:1px solid #3a3a44;border-radius:8px;width:34px;height:30px;cursor:pointer;font-size:15px}
.nav .fs{width:auto;padding:0 10px}
"""

_JS = """
const slides=[...document.querySelectorAll('.slide')];let i=0;
function show(n){i=(n+slides.length)%slides.length;
  slides.forEach((s,k)=>s.classList.toggle('active',k===i));
  document.getElementById('count').textContent=(i+1)+' / '+slides.length;}
function go(d){show(i+d)}
addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key===' ')go(1);
  if(e.key==='ArrowLeft')go(-1);
  if(e.key==='f'){const el=document.documentElement;
    document.fullscreenElement?document.exitFullscreen():el.requestFullscreen()}});
show(0);
"""


def render_slide_html(slide: dict, theme: Theme, img_uri: str | None = None) -> str:
    layout = LAYOUTS.get(slide.get("layout"), LAYOUTS["bullets"])
    fields = slide.get("fields") or {}
    inner = layout.render(fields, theme, img_uri)
    return f'<section class="slide">{inner}</section>'


def assemble_deck(slides_html: list[str], theme: Theme, title: str) -> str:
    fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
             '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;600&display=swap" rel="stylesheet">')
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html.escape(title)}</title>{fonts}"
        f"<style>:root{{{theme.css_vars()}}}{_CSS}</style></head><body>"
        f'<div class="stage">{"".join(slides_html)}</div>'
        '<div class="nav"><button onclick="go(-1)">‹</button>'
        '<span id="count"></span><button onclick="go(1)">›</button>'
        '<button class="fs" onclick="document.documentElement.requestFullscreen()">⛶</button></div>'
        f"<script>{_JS}</script></body></html>"
    )


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------

def generate_html_deck_from_document(
    doc: Union[dict, str],
    output_path: Union[str, Path],
    *,
    theme: Union[str, Theme, None] = "auto",
    language: str | None = None,
    images: bool = False,
    research: bool = False,
    title: str | None = None,
) -> dict:
    """Editor document -> a Gamma-style native HTML deck (real text, no raster
    overlays). theme="auto" lets the model pick a palette from the content; a
    name from THEMES forces one. images=True generates an AI image for the
    title/feature panels (else themed gradients). Returns
    {output, slides, theme, usage}."""
    usage_before = tracker.snapshot()

    sections = parse_document(doc)
    if not sections:
        raise ValueError("Document has no headings/content to turn into slides.")
    brief = "\n\n".join(f"{s['heading']}: {s['text']}" for s in sections)[:3000]

    research_summary = ""
    if research:
        from .research import extract_keywords, web_research
        rr = web_research(brief, extract_keywords(brief))
        research_summary = rr.summary

    th = resolve_theme(theme, brief)
    slides = map_document_to_html_plan(
        sections, language=language, research_summary=research_summary)
    if not slides:
        raise ValueError("Could not map the document to any slide layouts.")

    slides_html = []
    for s in slides:
        img_uri = None
        layout = LAYOUTS.get(s.get("layout"), LAYOUTS["bullets"])
        if images and layout.needs_image:
            try:
                img_uri = _image_uri_for(s.get("fields") or {}, layout)
            except Exception:
                img_uri = None
        slides_html.append(render_slide_html(s, th, img_uri))

    deck_title = title or (slides[0].get("fields", {}).get("title")) or "Presentation"
    html_doc = assemble_deck(slides_html, th, deck_title)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")

    usage = tracker.snapshot() - usage_before
    return {
        "output": str(out),
        "slides": [{"layout": s["layout"]} for s in slides],
        "theme": th.name,
        "usage": {
            "total_tokens": usage.total_tokens,
            "requests": usage.requests,
            "estimated_cost_usd": round(usage.estimated_cost, 4),
        },
    }
