# Agent 6 — Theme / Palette

**Kind:** agentic (palette choice) + deterministic (recolor)
**Code:** `slide_skills/theme.py` →
`propose_palette` (agentic), `auto_map_palette` / `_contrast_safe` /
`apply_palette` / `retheme_svg` (deterministic)

## Role
Choose a color palette that fits the topic and recolor the template to it —
without breaking text/background contrast.

## Palette source (one of)
- `"auto"` → the planner/`propose_palette` picks (agentic).
- a **preset** name (`teal`, `forest`, `midnight`, …) → `PRESETS`.
- a custom `(primary, secondary, accent)` tuple.
- `None` → keep the template's original colors.

## Agentic part — `propose_palette(brief, palette)`
- GPT-4o maps every current color → a new hex, fitting the brief's mood.
- Constrained to: preserve each color's luminance (dark stays dark, light
  stays light), keep pure `#000`/`#fff`, limit hue count.
- Returns `{old_hex: new_hex}`. `guides/color_theme.md` is injected.

## Deterministic part — mapping + recolor
- `auto_map_palette(palette, target)` assigns roles by luminance/saturation:
  dark→primary, light→secondary, vivid→accent.
- `_contrast_safe(new, old)` re-anchors any replacement that would drift a
  color's brightness too far — this is what prevents the "teal text on teal
  background" failure. It binary-searches lightness to match the original.
- `retheme_svg` / `apply_palette` rewrite the hex values (SVG text or pptx XML).

## Input → Output
- **In:** template colors + a target palette (or brief, for `propose_palette`)
- **Out:** a contrast-safe `{old: new}` mapping applied to the deck

## Notes
- Recoloring only swaps colors that exist as hex values (shape fills, text,
  gradients, SVG). Colors baked into raster images don't change.
