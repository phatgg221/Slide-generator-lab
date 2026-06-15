# Slide Generator Lab

AI slide generation in Python. Take a template (a Canva/PowerPoint `.pptx`, or
a hand-designed SVG collection), and generate a finished deck whose **text,
colors, images, and animations** are produced by AI to fit a topic — while the
**layout stays exactly as designed**.

Built as composable skills so the whole thing can be wired into a FastAPI app.
Published on PyPI as [`slide-skills`](https://pypi.org/project/slide-skills/).

---

## Install

**As a library (use in any project):**
```bash
pip install slide-skills                 # latest release from PyPI
# or, the bleeding edge straight from source:
pip install "git+https://github.com/phatgg221/Slide-generator-lab.git"
```

**For development (edit the code, changes apply instantly):**
```bash
git clone https://github.com/phatgg221/Slide-generator-lab.git
cd Slide-generator-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                         # editable install
```

Optional extras:
```bash
pip install "slide-skills[svg-convert]"  # PyMuPDF, for .pptx -> SVG conversion
pip install "slide-skills[all]"          # everything optional
```

## Requirements

| What | Needed for | Notes |
|---|---|---|
| **`OPENAI_API_KEY`** | any AI step (text, images, planning) | put in env or a `.env` file |
| Python ≥ 3.9 | everything | |
| `resvg-py` (auto-installed) | rendering SVG/web decks | bundled, no system deps |
| `TAVILY_API_KEY` + `pip install "slide-skills[search]"` | live web research | optional; without it, research falls back to OpenAI web-search then model knowledge |
| **LibreOffice** | `svg_template_maker` only (.pptx → SVG) | `brew install --cask libreoffice`; optional |

Environment variables (all optional):
```bash
OPENAI_API_KEY=sk-...            # required for AI calls
OPENAI_TEXT_MODEL=gpt-4o         # default
OPENAI_IMAGE_MODEL=gpt-image-1   # skip image-model auto-detection
TAVILY_API_KEY=tvly-...          # enables Tavily web search (pip install "slide-skills[search]")
SLIDE_TEMPLATES_DIR=/path/to/svg/templates   # where your SVG collections/categories live
SLIDE_LIBRARY_DIR=/path/to/pptx/templates    # where your .pptx templates live
SLIDE_GUIDES_DIR=/path/to/guides             # design-taste markdown injected into prompts
```
The two `*_DIR` vars are the key to using this as an installed package: set
them once and the library finds your templates wherever you keep them — your
designs live outside the code package.

---

## Two paths

The project supports two delivery targets that share most of the same skills:

| | **PPTX path** | **Web path** (current focus) |
|---|---|---|
| Output | Downloadable PowerPoint file | Self-contained animated HTML for your website |
| Template source | Canva/PowerPoint `.pptx` | Hand-designed SVG collections (Figma/Inkscape) |
| Animation | PowerPoint transitions + entrance effects | Native SVG/CSS animation (Canva-like) |
| Main CLI | `examples/build_course_deck.py` | `examples/web_deck.py` |

The web path is preferred because SVG keeps text editable, colors remappable,
and animations playable in the browser — and it needs no desktop renderer.

---

## How it works (agent flow)

A deck is produced by a chain of focused agent steps. You can run the whole
chain (topic → deck) or jump in at any stage (e.g. supply your own plan).

```
  topic / brief                          templates on disk (SVG collections
       │                                  or category folders + category.json)
       ▼                                            │
  ┌─────────────┐                                   │
  │ 1. Keywords │  GPT-4o pulls the core topics     │
  └─────────────┘                                   │
       ▼                                             │
  ┌─────────────┐  Tavily → OpenAI web_search →     │
  │ 2. Research │  model-knowledge. Facts, stats,   │
  └─────────────┘  sources (grounded brief)         │
       ▼                                             │
  ┌─────────────┐  GPT-4o decides slide count,      │
  │ 3. Plan     │  categories/types, order, theme ◄─┘ (knows what templates exist)
  └─────────────┘
       ▼
  ┌──────────────────┐  per slide: schema-fit shortlist + GPT-4o
  │ 4. Pick variant  │  tiebreak → best design for the data
  └──────────────────┘  (category library only)
       ▼
  ┌─────────────┐  GPT-4o writes each {{placeholder}} within its
  │ 5. Write    │  character budget (lists for multi-line slots)
  └─────────────┘
       ▼
  ┌─────────────┐  contrast-safe recolor to the chosen palette
  │ 6. Theme    │  (AI-picked, preset, custom, or keep original)
  └─────────────┘
       ▼
  ┌─────────────┐  optional: gpt-image-1 photos OR GPT-4o SVG
  │ 7. Images   │  vector art (~5× cheaper) into image slots
  └─────────────┘
       ▼
  ┌─────────────┐  fill SVGs → self-contained animated HTML deck
  │ 8. Assemble │  (or .pptx). Returns output path + usage (tokens/$)
  └─────────────┘
```

| Step | Agent / skill | Model / backend | Optional? |
|---|---|---|---|
| 1 Keywords | `extract_keywords` | GPT-4o | no |
| 2 Research | `web_research` | Tavily › OpenAI web_search › model | yes (`research`) |
| 3 Plan | `plan_deck` | GPT-4o | skip if you pass a plan |
| 4 Pick variant | `select_and_fill_slide` | schema-fit + GPT-4o | category libraries only |
| 5 Write | `generate_deck_content` | GPT-4o | no |
| 6 Theme | `theme.py` | pure code (+ optional GPT-4o palette) | yes |
| 7 Images | `generate_image` / `generate_svg_image` | gpt-image-1 / GPT-4o | yes |
| 8 Assemble | `html_deck` / `svg_slide_renderer` | pure code | no |

Two ready-made entry points bundle these steps:
- **`generate_web_deck(collection, brief, …, research=True)`** — the full
  flow over one collection: (1·2 with `research=True`) ·3·5·6·(7)·8.
- **`generate_deck_from_plan(plan, library_dir, …)`** — steps 4·5·6·8 where
  your plan already names a category per slide and the agent picks the variant.

Every entry point returns a `usage` block (tokens + estimated USD) for the run.

**Per-agent docs:** each step has an "agent card" in [`agents/`](agents/) —
role, input/output, model/backend, and decision logic (e.g. how the researcher
searches the web, how the category→variant mapper picks a design).

---

## Use as a Python library

Once installed, import the skills from anywhere:

```python
from slide_skills import generate_web_deck

# Topic -> animated HTML deck (writes the file, returns a summary dict)
result = generate_web_deck(
    collection="starter",                 # folder under SLIDE_TEMPLATES_DIR
    brief="Khóa học nhập môn Machine Learning",
    output_path="out/deck.html",
    palette="teal",                       # "auto" | preset name | (primary, secondary, accent) | None
    language="Vietnamese",
    animation="rise",                     # rise | fade | scale | none
)
print(result["output_path"], result["slides"])
print(result["usage"]["report"])          # tokens + estimated USD for this call
```

Every `generate_*` call returns a `usage` block with the total cost of that run:
```python
result["usage"]   # {input_tokens, output_tokens, total_tokens, requests,
                  #  estimated_cost_usd, report}
```

**Category library + variant-selecting agent** (your plan names categories; the
agent picks the best design variant per slide):
```python
from slide_skills import generate_deck_from_plan, scan_template_library

lib = scan_template_library("templates")     # discover categories + variants
print(lib.category_map())                     # registry for a UI / planner

plan = {"title": "ML 101", "slides": [
    {"category": "Title Slide", "topic": "Intro to Machine Learning"},
    {"category": "KPI & Big Numbers", "talking_points": ["78%", "3x", "12M"]},
    {"category": "Conclusion & Summary", "talking_points": ["Recap", "Next steps"]},
]}
generate_deck_from_plan(plan, "templates", "out/deck.html", palette="auto", language="Vietnamese")
```

**From an editor document** (ProseMirror/TipTap JSON) — parse → infer a
category per section → optionally research → theme → variant-fill → deck:
```python
from slide_skills import generate_deck_from_document

result = generate_deck_from_document(
    editor_doc,                 # {"type":"doc","content":[heading, paragraph, bulletList, ...]}
    "templates",                # your category library
    "out/deck.html",
    palette="auto",             # agent picks the theme from the content
    research=True,              # enrich sections with web facts first
    images=True,                # fill <image> slots; image_source "svg" (cheap) or "ai"
    language="Vietnamese",
)
print(result["plan"])           # the inferred category-per-slide plan
print(result["usage"]["report"])
```

**Add a collection at runtime** (e.g. a user uploads a Figma export):
```python
from slide_skills import import_collection
import_collection("/path/to/figma_export_folder", "my_style")   # copies + validates
```

**Track cost of any run:**
```python
from slide_skills import usage_tracker
before = usage_tracker.snapshot()
# ... generate ...
print((usage_tracker.snapshot() - before).report())
```

**Per-user API keys** (multi-tenant service — each user supplies their own
OpenAI/Tavily key): wrap calls in `use_keys`. It's async-task-local, so keys
never leak across concurrent requests. Without it, keys come from the env.
```python
from slide_skills import use_keys, generate_web_deck

with use_keys(openai_key=user_openai_key, tavily_key=user_tavily_key):
    generate_web_deck("starter", topic, "out/deck.html")
```

In a **FastAPI** app, wrap blocking calls in a thread and scope keys per request:
```python
import asyncio
from fastapi import FastAPI
from fastapi.responses import FileResponse
from slide_skills import generate_web_deck, use_keys

app = FastAPI()

def _run(topic, collection, openai_key):
    with use_keys(openai_key=openai_key):       # set inside the worker thread
        return generate_web_deck(collection, topic, "out/deck.html")

@app.post("/generate")
async def generate(topic: str, openai_key: str, collection: str = "starter"):
    await asyncio.to_thread(_run, topic, collection, openai_key)
    return FileResponse("out/deck.html", media_type="text/html")
```
(Set `SLIDE_TEMPLATES_DIR` so the app finds your collections. Set keys inside
the thread/worker that runs the generation, not only on the request coroutine.)

---

## Quick start (CLI) — Web deck from an SVG collection

```bash
# 1. See available collections
.venv/bin/python examples/web_deck.py list

# 2. Validate a collection — what placeholders did it find? (free, offline)
.venv/bin/python examples/web_deck.py check starter

# 3. Visual preview with stub text (free, offline)
.venv/bin/python examples/web_deck.py demo starter
open out/starter_demo.html

# 4. Generate a real deck from a topic (~$0.02)
.venv/bin/python examples/web_deck.py generate starter \
    "Khóa học nhập môn Machine Learning" -o out/ml_deck.html --language Vietnamese
open out/ml_deck.html
```

In the browser deck: **→/←** to navigate, **f** for fullscreen, elements
animate in as each slide appears.

Options: `--palette teal` (force a theme), `--animation rise|fade|scale|none`,
`--research` (run keyword extraction + web search first — the full flow),
`--language Vietnamese`.

---

## Designing your own SVG collections

You design collections once in Figma/Inkscape; every generated deck reuses
them. A collection is a folder of slide-type SVGs sharing one visual style:

```
svg_templates/<collection>/
  collection.json     # optional: description, palette, fonts, tags
  title.svg           # filename = slide type the planner picks from
  statistic.svg
  comparison.svg ...
```

Rules (see `svg_templates/README.md` for the full guide):

- **Export SVG with "Outline Text" UNCHECKED** — text must stay live `<text>`.
- Placeholders are the text content: `{{title}}`, `{{quote|120}}` (120-char
  budget), `{{body.1}}` / `{{body.2}}` (multi-line).
- One uniform style per placeholder (don't bold half a word — it splits the text).
- Name files by function (`title`, `statistic`, `quote`…); use common fonts.

Then `web_deck.py check` / `demo` your folder before spending on generation.

---

## Tuning the AI's taste (design guides)

The agents' design sense lives in editable markdown, injected into the prompts
at runtime — change the deck's aesthetic without touching code:

```
guides/
  color_theme.md   # palette principles, contrast rules, topic→palette table
  style.md         # deck structure, layout choice, writing style, what to avoid
```

- `color_theme.md` → injected into `propose_palette` and `plan_deck`
- `style.md` → injected into `plan_deck`, the SVG content writer, and the
  variant-selecting agent

Edit a guide and the next generation follows the new rules — no rebuild. Guides
are optional (a missing file is simply ignored). Point `SLIDE_GUIDES_DIR` at a
different folder to swap in a per-brand guide set. Keep them crisp — every line
costs prompt tokens on each call.

---

## Category library + variant-selecting agent

For richer decks, organize templates into **categories**, each holding several
**variant** designs for the same layout function. The user's plan names a
category per slide; an agent picks the best-fitting variant for the data.

```
templates/
  TITLE_SLIDE/
    category.json        # optional: descriptions guiding variant choice
    centered.svg         # variants — multiple designs, same purpose
    left_aligned.svg
  KPI_BIG_NUMBERS/
    category.json
    three_stats.svg
    list_style.svg
```

`category.json` (optional but recommended — it's the "map" the agent reads):
```json
{
  "description": "Highlight key metrics with large, scannable numbers.",
  "variants": {
    "three_stats": "Three stat callouts — use for 2-3 key numbers.",
    "list_style":  "A vertical list — use for 4+ numbers or rankings."
  }
}
```

How a variant gets chosen, per slide:
1. **schema-fit shortlist** (code) — keep variants whose slot count fits the data
2. **AI tiebreak** (GPT-4o) — read each finalist's description + slots and the
   slide content, pick the best, and write its text

Adding designs is pure data:
- **New variant** → drop a `.svg` in the category folder (instantly usable;
  add a `category.json` line so the agent knows when to choose it).
- **New category** → make a new folder; it appears in `category_map()` automatically.

Category names match plan labels ignoring case/spaces/`&`/`-`/`_`
(`"KPI & Big Numbers"` → `KPI_BIG_NUMBERS`), but not plurals — name folders to
match your plan labels.

---

## Quick start — PowerPoint deck from a .pptx template

```bash
# Ingest any .pptx into the reusable template library (cleans junk, classifies slides)
.venv/bin/python examples/prepare_template.py "~/Downloads/My Design.pptx" my_template

# See what's editable (free, offline)
.venv/bin/python examples/test_template.py my_template

# Full pipeline: research -> plan -> write -> images -> theme -> animate
.venv/bin/python examples/build_course_deck.py library/my_template.pptx \
    "your topic" --transition fade --animate fade -o out/deck.pptx
```

Cost controls: `--no-research`, `--no-images`, `--svg-images` (cheap vector
illustrations instead of AI photos).

---

## Skills reference (`slide_skills/`)

**Foundation**
- `config.py` — OpenAI client + model config from `.env`
- `usage.py` — token & cost tracking across all AI calls (`usage_tracker`)
- `template_parser.py` — parse a `.pptx` into a fill-spec; classify text roles,
  char budgets; skip tip-bubbles & navigation buttons

**Research → Plan → Write**
- `research.py` — `extract_keywords`, `web_research`
- `planner.py` — `plan_deck`: AI picks slide count, types, order, theme
- `content_generator.py` — `generate_content`: AI writes budget-aware text
- `agent.py` — `SlideGeneratorAgent`: fill one template from a brief
- `pipeline.py` — `CourseDeckPipeline`: the full chained pipeline

**Images**
- `image_generator.py` — `generate_image`: AI photos, auto-detects account's model
- `svg_image_generator.py` — `generate_svg_image`: GPT-4o vector art (~5× cheaper)

**Filling & assembly**
- `slide_filler.py` — write text keeping formatting, auto-shrink overflow, swap images
- `assembler.py` — build a deck by picking/reordering/repeating library slides

**Templating**
- `template_maker.py` — `prepare_template`: ingest + clean + AI-classify a `.pptx`
- `merge_template.py` — `{{placeholder}}` form + schema; AI fills; render
- `svg_template_maker.py` — `.pptx` → folder of live-text SVGs *(needs LibreOffice/PowerPoint)*

**Theme & motion**
- `theme.py` — contrast-safe recoloring, 8 presets, `propose_palette`
- `transitions.py` — PowerPoint slide transitions
- `animations.py` — PowerPoint element entrance animations

**Web decks**
- `svg_collections.py` — scan collections, fill placeholders, retheme,
  `import_collection`, `generate_web_deck`
- `svg_categories.py` — category library + variant-selecting agent:
  `scan_template_library`, `select_and_fill_slide`, `generate_deck_from_plan`
- `html_deck.py` — build a self-contained animated HTML presentation
- `svg_slide_renderer.py` — filled SVGs → PNG → `.pptx` export

---

## Command-line tools (`examples/`)

| Command | Purpose |
|---|---|
| `web_deck.py` | SVG collections → animated web deck (`list`/`check`/`demo`/`generate`) |
| `build_course_deck.py` | Full pipeline → `.pptx` |
| `generate_deck.py` | Fill one template from a brief |
| `prepare_template.py` | Ingest a `.pptx` into the template library |
| `test_template.py` | Dry-run marker fill — see what's editable (free) |
| `recolor_deck.py` | Re-theme an existing deck's colors |
| `merge_deck.py` | `{{placeholder}}` workflow (make/render/generate) |

---

## What can be customized per deck

- **Words** — every `{{placeholder}}` is AI-written, any language
- **Colors** — preset, AI-picked, or custom; always contrast-safe
- **Animation** — rise / fade / scale / none (web) or PowerPoint effects (pptx)
- **Slides** — the planner chooses which template types to use, and their order

Fixed by design: your layout, and (for now) fonts.

---

## Tests (offline, no API key)

```bash
.venv/bin/python tests/test_offline_pipeline.py   # parse / fill / image swap
.venv/bin/python tests/test_assembler.py          # library assembly
```

---

## Known limits

- **Canva exports lose animation and live text.** `.pptx` from Canva is static;
  Canva SVG outlines all text. Design real SVG templates in Figma/Inkscape.
- **`svg_template_maker.py` needs a renderer.** Install LibreOffice
  (`brew install --cask libreoffice`) for headless, server-ready conversion;
  the desktop-PowerPoint fallback is fragile.
- **Charts aren't data-driven yet.** Chart-style slides render as designed art,
  not recomputed from numbers.
- **FastAPI app** is a later milestone; all skills are import-ready for it.

---

## Releasing a new version (maintainers)

```bash
# 1. bump version in BOTH pyproject.toml and slide_skills/__init__.py
# 2. rebuild fresh and publish
rm -rf dist && python -m build
twine upload dist/*          # username: __token__   password: your pypi-... token
# 3. tag it
git tag v0.2.12 && git push origin main --tags
```
PyPI versions are permanent — never reuse a number; bump to the next one.
