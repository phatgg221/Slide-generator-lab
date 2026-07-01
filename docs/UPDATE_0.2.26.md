# slide-skills 0.2.26 — Update Brief (for an implementing agent)

This document describes what changed in `slide-skills` 0.2.25 → 0.2.26 and how
to use it. It is self-contained: an agent building a web app on top of this
library can act on it without extra context.

Install: `pip install --upgrade slide-skills`  (PyPI package name: `slide-skills`).

---

## 1. TL;DR of the change

The library now has **two ways** to turn a document into an animated web deck:

1. **Native HTML themes (NEW, recommended)** — `generate_html_deck_from_document(...)`.
   Every slide is real HTML/CSS. Text reflows, never overlaps, is vector-crisp,
   and lists are dynamic (add items → grid reflows). ~$0.01/deck.
2. **Extracted templates (existing)** — `extract_template_smart(...)` then
   `generate_deck_from_document(...)`. Lets you reuse a specific Canva/PPTX
   design, but renders text over a raster background (quality ceiling). ~$0.05/deck.

**Default to path 1 for new work.** Use path 2 only when a specific imported
design is required.

Both take the SAME input document shape and both output ONE self-contained
`.html` file (embeddable via `<iframe>` or served directly).

---

## 2. Input: the document shape

Both entry points accept a ProseMirror / TipTap JSON document (dict or JSON
string). Sections are split on headings; each section becomes one slide.

```json
{
  "type": "doc",
  "content": [
    { "type": "heading", "attrs": { "level": 1 },
      "content": [{ "type": "text", "text": "Deck Title" }] },
    { "type": "paragraph",
      "content": [{ "type": "text", "text": "Intro sentence." }] },

    { "type": "heading", "attrs": { "level": 2 },
      "content": [{ "type": "text", "text": "Section heading" }] },
    { "type": "bulletList", "content": [
      { "type": "listItem", "content": [{ "type": "paragraph",
        "content": [{ "type": "text", "text": "A point" }] }] }
    ]},
    { "type": "blockquote", "content": [{ "type": "paragraph",
      "content": [{ "type": "text", "text": "A testimonial." }] }] }
  ]
}
```

Number of slides follows the DOCUMENT structure (one slide per section), not a
fixed template count.

---

## 3. Primary API — native HTML themes (path 1)

```python
from slide_skills import generate_html_deck_from_document

result = generate_html_deck_from_document(
    doc,                       # dict | JSON str  (the shape above)
    output_path,               # str | Path       -> writes one .html file
    *,
    theme="auto",              # "auto" (AI picks) | a THEMES name | a Theme object | None (no theme)
    language=None,             # e.g. "English", "Vietnamese"; None = document's language
    images=False,              # True -> AI image in title/feature panels (costs extra); else gradient
    research=False,            # True -> web-research to ground facts before writing (needs TAVILY_API_KEY)
    title=None,                # override deck <title>; defaults to the first slide's title
)
# returns:
# {
#   "output": "path/to/deck.html",
#   "slides": [{"layout": "title"}, {"layout": "stats"}, ...],
#   "theme":  "custom" | "<theme name>",
#   "usage":  {"total_tokens": int, "requests": int, "estimated_cost_usd": float}
# }
```

### Themes
Built-in names (pass as `theme=`): `editorial-warm`, `midnight`, `clean-slate`,
`forest`, `sunset`. `theme="auto"` lets the model pick or invent a cohesive
palette from the deck's subject.

```python
from slide_skills import THEMES, Theme, propose_theme
list(THEMES)                      # the built-in names
propose_theme("a fintech pitch")  # -> Theme (AI-chosen/invented)
# custom palette:
Theme("brand", bg="#0E1116", ink="#EAF0F7", muted="#9fb0c3",
      accent="#5B9BFF", rule="#2a3543", panel_a="#1c3a6e", panel_b="#0a1526")
```

### Layouts (auto-selected per section)
`title, agenda, section, bullets, stats, quote, comparison, feature, closing`
(`slide_skills.LAYOUTS` is the registry). List-based layouts (`stats`,
`bullets`, `comparison` points, `agenda`) are **data-driven grids**: pass N
items and the CSS grid reflows onto new rows automatically — no fixed slot
count. This is the "add item" behaviour; adding an item = appending to the list
and re-rendering.

### Output HTML
- One self-contained file (fonts via Google Fonts `<link>`; needs internet when
  viewed — fallbacks to system fonts offline).
- Keyboard nav (← →, space), `f` = fullscreen, on-screen nav + slide counter.
- Staggered CSS entrance animations per slide.
- Fixed 16:9 slides. A single slide can't hold unlimited items (~6–9 max before
  it's cramped) — that's the only real constraint vs a scrolling web page.

---

## 4. Secondary API — extracted templates (path 2, existing + fixed)

Use only to reuse a specific imported design.

```python
from slide_skills import extract_template_smart, generate_deck_from_document

# ONE TIME per source design: turn a .pptx into a category-folder template.
extract_template_smart(
    "design.pptx", "myname",
    library_dir="svg_templates",   # writes svg_templates/myname_template/<CATEGORY>/...
    use_ai=True,                   # AI classifies slides + writes field descriptions
)

# MANY TIMES: generate a deck from any document using that template.
result = generate_deck_from_document(
    doc, "svg_templates/myname_template", "deck.html",
    palette="auto",                # "auto" | a preset name | None (keep template colors)
    language="English",
    images=False,                  # True -> images (image_source="svg" cheap | "ai" photo)
)
```

### 0.2.25 fixes on this path (already applied)
- **Agenda is never blank**: the agenda slide is filled from the deck's real
  section headings, plus a backfill guarantees every text slot has content.
- **Text no longer overflows/collapses**: each line's font size shrinks to fit
  its box (natural proportions, no squished glyphs).

### Discovering an extracted template (descriptions for the agent)
`extract_template_smart(...)` returns a self-describing catalog, and writes a
`library.json` manifest in the template folder:

```python
r = extract_template_smart("design.pptx", "myname", library_dir="svg_templates")
r["categories"]   # [{"category","purpose","fields":{name:{type,desc,max_chars}}}]
r["manifest"]     # path to svg_templates/myname_template/library.json (one-file catalog)
```

To load an existing template's catalog with descriptions + slot specs:

```python
from slide_skills import scan_template_library
lib = scan_template_library("svg_templates/myname_template")
catalog = lib.category_map(include_fields=True)
# [{"category","purpose","variants":[{"name","description","fields":{...}}]}]
```

Feed `catalog` to your agent so it knows WHICH slide to use and WHAT each slot
expects. (Requires 0.2.27+.)

### Migration note (IMPORTANT)
The overflow fix relies on a `data-w` attribute the extractor now emits. **Any
template extracted before 0.2.25 must be re-extracted once** to get it.
Re-extraction uses the exact same call. Hand-authored SVG collections don't
need it (the fix is a no-op there).

---

## 5. API keys (multi-tenant safe)

Keys resolve from a context var first, then env vars (`OPENAI_API_KEY`,
`TAVILY_API_KEY`). For a web server, set per-request keys with `use_keys`:

```python
from slide_skills import use_keys

with use_keys(openai_key=user_openai_key, tavily_key=user_tavily_key):
    result = generate_html_deck_from_document(doc, "deck.html", theme="auto")
```

Text uses OpenAI `gpt-4o` (override with env `OPENAI_TEXT_MODEL`). Images use
the account's available image model (gpt-image-1 / dall-e-3). Web research uses
Tavily when `TAVILY_API_KEY` is set.

---

## 6. FastAPI integration sketch

```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from slide_skills import generate_html_deck_from_document, use_keys
import tempfile, os

app = FastAPI()

class DeckRequest(BaseModel):
    doc: dict
    theme: str = "auto"
    language: str | None = None
    images: bool = False

@app.post("/generate", response_class=HTMLResponse)
def generate(req: DeckRequest):
    out = os.path.join(tempfile.mkdtemp(), "deck.html")
    with use_keys(openai_key=os.environ["OPENAI_API_KEY"]):
        generate_html_deck_from_document(
            req.doc, out, theme=req.theme,
            language=req.language, images=req.images)
    return open(out, encoding="utf-8").read()
```

Store/serve the returned HTML however you like (return inline, save to object
storage, embed via `<iframe>`). The file is self-contained.

---

## 7. Cost (approx, gpt-4o pricing)
- Native HTML deck: **~$0.01** (2 requests: theme + section→layout mapping).
- Extracted-template deck: **~$0.05** (per-slide fill calls).
- `images=True`: add ~$0.04–0.19 per generated image (gpt-image-1).
- `research=True`: adds a Tavily call + a small grounding token cost.

`result["usage"]` reports exact tokens/requests/cost per call.

---

## 8. What to build on
For a new product, build on **path 1 (`generate_html_deck_from_document`)**:
best looking, cheapest, no overlap/blank-slot failure modes, and lists are
dynamic. Keep path 2 available for the "import my exact Canva design" case.

Suggested near-term enhancements (not yet implemented):
- Count-aware sizing on the `stats` grid (auto-balance 6+ cards on 16:9).
- More layouts (timeline, big-image, team, pricing) and more themes.
- A `.pptx`/PDF export from the HTML layouts.
