# Changelog

## 0.2.27

### Extracted templates are now self-describing
- **`extract_template_smart(...)` return value now carries descriptions.**
  Previously it returned only `category / text_slots / image_slots`, so an agent
  reading the return had no idea what each slide type was for. It now returns:
  - `categories`: `[{category, purpose, fields:{name:{type,desc,max_chars}}}]`
  - `manifest`: path to a new **`library.json`** written in the template folder —
    one file listing every category, its purpose, and its fillable fields, so an
    agent can read a single file to understand the whole template.
  - (still) `template_dir`, `slides`, `usage`.
- **`TemplateLibrary.category_map(include_fields=True)`** — the loader's catalog
  method can now include each variant's slots (name → type/desc/budget), so
  `scan_template_library(dir).category_map(include_fields=True)` gives an agent
  the complete "which slide + what content" picture in one call.
- No breaking changes; existing return keys are preserved.

## 0.2.26

### New: native HTML themes (Gamma-style web decks)
- **`generate_html_deck_from_document(doc, output_path, *, theme="auto", language=None, images=False, research=False, title=None)`**
  — renders a document (ProseMirror/TipTap JSON) into a self-contained animated
  HTML deck where every slide is **real HTML/CSS**, not text painted over a
  raster. Text reflows, never overlaps, and stays vector-crisp at any zoom.
- **9 layouts**, auto-picked per section: `title, agenda, section, bullets,
  stats, quote, comparison, feature, closing`. All list-based layouts
  (`stats`, `bullets`, `comparison`, `agenda`) are **data-driven grids** — pass
  N items and the grid reflows onto new rows automatically (Gamma-style
  "add item"); no fixed slot count.
- **Theming**: 5 built-in themes (`editorial-warm, midnight, clean-slate,
  forest, sunset`) plus `propose_theme(brief)` — the model picks or invents a
  cohesive palette from the deck's subject. Design tokens (palette + fonts +
  type scale) drive the whole look. Serif display (Fraunces) + Inter body.
- **Optional AI images**: `images=True` fills the title/feature panels with a
  generated image; otherwise a themed gradient panel is used (free).
- Much cheaper than the extracted-template path: ~**$0.01/deck** (2 model
  requests: theme + mapping) vs ~$0.05.
- New exports: `generate_html_deck_from_document`, `propose_theme`, `THEMES`,
  `Theme`, `LAYOUTS`.

## 0.2.25

### Fixes for extracted templates (`extract_template_smart`)
- **Agenda / cards are never blank.** Extracted templates bake cards, chips and
  dividers into the background image, so an unfilled slot used to render an
  empty card. `generate_deck_from_document` now feeds the agenda slide the
  deck's real section headings, and a new backfill guarantees every text slot
  gets content (number-ish slots → `01/02/…`, others cycle the slide's points).
- **Text no longer collapses/overflows into neighbouring cards.**
  `fit_text_to_boxes` shrinks a line's **font size** to fit its box (the
  extractor now records `data-w` per `<text>`). Earlier text could overflow
  sideways and collide; it now scales down at natural proportions (no condensed
  "stiff" glyphs), down to a 7pt floor.
