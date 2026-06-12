# SVG Template Collections — Authoring Guide

A **collection** = one folder = one visual style. Each `.svg` inside is one
slide type; the filename is the type name the AI planner sees (`title.svg`,
`statistic.svg`, `chart.svg`, …). See `starter/` for a working reference.

## Designing in Figma

1. Design each slide as a **1440 × 810** frame (16:9).
2. Type placeholders as the **literal text content**:
   - `{{name}}` — single line
   - `{{name|40}}` — with a character budget (recommended! the AI treats it
     as a hard limit; without it the budget is estimated from font size)
   - `{{name.1}}`, `{{name.2}}` — multi-line lists (AI supplies one line each)
   - Anything *not* in `{{ }}` stays exactly as designed (numbers, labels, decorations)
3. Export: select the frame → Export → SVG → **uncheck "Outline Text"**.
   (Text exported as outlines cannot be filled — that's the Canva problem.)
4. Drop the exported `.svg` files into your collection folder.

## Rules that keep rendering reliable

- **Fonts**: use widely available ones (`Helvetica, Arial`, `Georgia`,
  `Times New Roman`) or put the `.ttf`/`.otf` files in the collection folder.
- **Colors as 6-digit hex** (`#1F2A44`) — that's what re-theming rewrites.
  Figma exports this way by default.
- One `<text>` per line of text. Avoid Figma auto-resize text boxes wrapping
  one paragraph into multiple lines — make each line its own text layer.
- No embedded photos unless they're part of the style (they won't re-theme).
- Group related decorations: each **top-level element animates as one unit**
  in the web deck (staggered entrance, top to bottom of the file).

## collection.json (optional but recommended)

```json
{
  "description": "When the planner should pick this style",
  "palette": ["1F2A44", "F6F1E7", "E4654F"],
  "tags": ["editorial", "warm"]
}
```

## Test a collection

```bash
.venv/bin/python examples/web_deck.py check <collection>     # placeholders + budgets
.venv/bin/python examples/web_deck.py demo <collection>      # offline filled preview deck
.venv/bin/python examples/web_deck.py generate <collection> "your topic" -o out/deck.html
```
