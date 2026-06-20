# Using `slide-skills` in your own repo

A practical checklist for adding AI slide generation to another project.
The library is the engine; you bring the **templates** (designs) and **keys**.

---

## 1. Install

```bash
pip install slide-skills            # core
pip install "slide-skills[search]"  # + Tavily web research (optional)
```
(Or pin a version: `slide-skills==0.2.19`.)

## 2. Bring your data (lives in YOUR repo, not the package)

```
your-repo/
  templates/                 # category library (point SLIDE_TEMPLATES_DIR here)
    TITLE_SLIDE/
      standard.svg           # live-text SVG with {{placeholders}}
      standard.schema.json   # optional: field types/desc
      category.json          # when to use it + variant descriptions
    KPI_BIG_NUMBERS/ ...
    IMAGE_GALLERY/           # any template can have <image href="{{name}}"> slots
  guides/                    # optional design-taste (point SLIDE_GUIDES_DIR here)
    color_theme.md
    style.md
```
Copy the `templates/` and `guides/` folders from this repo as a starting point,
then add your own Figma-designed SVGs.

## 3. Configure (environment)

```bash
OPENAI_API_KEY=sk-...                 # required
TAVILY_API_KEY=tvly-...               # optional (web research + references slide)
SLIDE_TEMPLATES_DIR=/abs/path/templates
SLIDE_GUIDES_DIR=/abs/path/guides     # optional
OPENAI_IMAGE_MODEL=gpt-image-1        # optional
```

## 4. Call it — three entry points

```python
from slide_skills import (
    generate_deck_from_document,   # editor doc (ProseMirror/TipTap JSON) -> deck
    generate_web_deck,             # a topic/brief + one collection -> deck
    generate_deck_from_plan,       # a plan that already names categories -> deck
    scan_template_library,         # discover categories+variants (for a UI)
)

# Most common: a rich-text document from your editor
result = generate_deck_from_document(
    doc,                       # {"type":"doc","content":[heading, paragraph, ...]}
    "templates",               # or omit and rely on SLIDE_TEMPLATES_DIR
    "out/deck.html",
    palette="auto",            # "auto" | preset | (p,s,a) | None
    language="English",
    research=True,             # web facts + a references slide (needs Tavily)
    images=True,
    image_source="ai",         # "ai" = gpt-image-1 (polished) | "svg" = cheap icons
)
# result -> {output_path, slides:[{category,variant}], plan, sources, usage, warnings}
print(result["usage"]["report"])      # tokens + estimated USD
```

## 5. Wire into a web app (FastAPI sketch)

```python
import asyncio, uuid
from fastapi import FastAPI
from fastapi.responses import FileResponse
from slide_skills import generate_deck_from_document, use_keys

app = FastAPI()

def _build(doc, openai_key, out):
    with use_keys(openai_key=openai_key):          # per-user key, concurrency-safe
        return generate_deck_from_document(doc, "templates", out,
                                           palette="auto", images=True, image_source="ai")

@app.post("/generate")
async def generate(doc: dict, openai_key: str):
    out = f"storage/{uuid.uuid4().hex[:8]}.html"
    res = await asyncio.to_thread(_build, doc, openai_key, out)   # generation is blocking
    return {"deck": out, "slides": res["slides"], "usage": res["usage"]}

@app.get("/templates")                              # for a "pick a layout" UI
def templates():
    return scan_template_library("templates").category_map()
```
For production, move `_build` to a background worker (Celery/RQ/ARQ) and poll —
a deck with AI images takes 1–3 min.

## 6. Add a new template (no code change)

1. Design an SVG in Figma with **live text** (uncheck "Outline Text"); write
   `{{name}}` where text goes, `<image href="{{img}}">` where a picture goes.
2. Drop it in `templates/<CATEGORY>/<variant>.svg`.
3. Add a `category.json` line describing when to use it (this is how the agent
   chooses it). Optionally a `<variant>.schema.json` for field types.

---

## Cost & knobs
- Text-only deck: ~$0.03–0.05. + web research: +~$0.02. + AI images: ~$0.07 each.
- `research=False` / `image_source="svg"` for cheap drafts; `ai` + `research=True`
  for client-ready decks.
- Every call returns `result["usage"]` — log it for billing/limits.

## Gotchas
- Templates & guides are DATA — deploy them on the server (volume/git/S3), not
  in the pip package.
- Category names match plan labels ignoring case/spaces/`&`/`-`/`_`, not plurals.
- The references slide needs Tavily (or web_search) for real sources.
- Keep `starter`/`neon_dark`-style *collections* out of the category dir.
