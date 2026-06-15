# Agent 4 — Category → Variant Mapper

**Kind:** agentic (GPT-4o) on top of a deterministic schema-fit shortlist
**Code:** `slide_skills/svg_categories.py` →
`scan_template_library`, `shortlist_variants`, `select_and_fill_slide`,
`generate_deck_from_plan`

## Role
For each planned slide that names a **category**, pick the best **variant**
(one of several designs in that category) for the slide's data, then write its
text. This is the "mapper for slides based on categories."

## Library it maps over
```
templates/<CATEGORY>/<variant>.svg   + optional category.json
```
`scan_template_library(dir)` → `TemplateLibrary` with:
- `.categories`: `{CATEGORY: [Variant(name, placeholders, description), ...]}`
- `.descriptions`: `{CATEGORY: purpose}`
- `.category_map()`: registry for a UI/planner
- `.resolve(label)`: maps a plan label to a category key

## Step A — map plan label → category (deterministic)
`resolve("KPI & Big Numbers")` canonicalizes by lowercasing and stripping
spaces / `&` / `-` / `_` → matches folder `KPI_BIG_NUMBERS`. **Not** fuzzy on
plurals (`Number` ≠ `Numbers`) — folder names must match plan labels. No match
→ that slide is skipped with a warning.

## Step B — shortlist variants by schema fit (deterministic)
`shortlist_variants(variants, slide_content, k=4)`:
- `_content_size(slide_content)` = number of items implied (e.g. length of
  `talking_points`).
- `_capacity(variant)` = largest repeatable placeholder family (e.g. a
  3-stat layout has capacity 3).
- Rank variants: those that can hold all items first, then by closeness.
  Keep the top `k`.

## Step C — pick + fill (agentic, GPT-4o)
`select_and_fill_slide` sends the finalists' **descriptions + slot schemas**
and the slide content to GPT-4o in one JSON call. The model:
1. Chooses the variant whose description AND slots best fit the content.
2. Writes text for every placeholder within budget (arrays for multi-line).
Returns `{"variant": Variant, "texts": {...}}`. If the model names a variant
outside the shortlist, it falls back to the top shortlisted one.

## Input → Output (whole step)
- **In:** a plan `{"slides": [{"category", "topic"/"talking_points", ...}]}`
- **Out (via `generate_deck_from_plan`):** filled + themed SVGs assembled into
  an animated HTML deck; returns `{output_path, slides:[{category, variant}],
  warnings, usage}`.

## Injected guidance
`guides/style.md` is appended to the selection prompt (layout-fit rules).

## How to improve variant choice
Add a `category.json` per folder with a one-line `description` per variant —
the model uses it as "when to choose this design."
