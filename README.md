# Slide Generator Lab

AI slide generation in Python. Take a template (a Canva/PowerPoint `.pptx`, or
a hand-designed SVG collection), and generate a finished deck whose **text,
colors, images, and animations** are produced by AI to fit a topic — while the
**layout stays exactly as designed**.

Built as composable skills so the whole thing can be wired into a FastAPI app.

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

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # paste your OPENAI_API_KEY
```

Optional in `.env`:
```
OPENAI_IMAGE_MODEL=gpt-image-1   # set to skip image-model auto-detection
```

---

## Quick start — Web deck from an SVG collection

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
`--pptx` (also export a PowerPoint copy).

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
- `svg_collections.py` — scan collections, fill placeholders, retheme
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
