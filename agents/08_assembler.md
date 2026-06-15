# Agent 8 — Assembler

**Kind:** deterministic (no LLM)
**Code:** `slide_skills/html_deck.py` → `build_html_deck`;
`slide_skills/svg_slide_renderer.py` → `render_svg_deck` (pptx export);
`slide_skills/slide_filler.py` (pptx fill); `slide_skills/assembler.py`
(pptx library assembly)

## Role
Turn the filled, themed slides into the final deliverable.

## Web path — `build_html_deck(filled_svgs, output, *, title, animation)`
- Inlines each filled SVG into ONE self-contained `deck.html` (vectors stay
  crisp; text stays selectable).
- Adds vanilla JS/CSS: arrow-key / click navigation, slide counter, fullscreen.
- Injects staggered CSS entrance animations per slide (`rise|fade|scale|none`)
  and slide transitions — this is where the in-browser motion lives.
- Embeddable via `<iframe>` or served directly by FastAPI.

## PPTX path
- `slide_filler.py` writes text/images into the .pptx keeping formatting and
  shrinking overflow; `assembler.py` picks/reorders/clones library slides;
  `render_svg_deck` can rasterize filled SVGs into a .pptx of slide images.

## Input → Output
- **In:** list of filled SVG strings (or a filled pptx)
- **Out:** a deck file on disk; the calling entry point returns
  `{output_path, slides, usage, ...}`.

## Notes
- Fully deterministic — same inputs produce the same file. No API cost.
- HTML decks are single files with no external assets (easy to store/serve).
