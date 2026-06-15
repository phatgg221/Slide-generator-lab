# Agent 5 — Content Writer

**Kind:** agentic (GPT-4o)
**Code:**
- collection path: `slide_skills/svg_collections.py` → `generate_deck_content`
- category path: writing happens inside Agent 4 (`select_and_fill_slide`)
- pptx path: `slide_skills/content_generator.py` → `generate_content`

## Role
Write the actual slide text into each `{{placeholder}}`, respecting its
character budget and line count, in a consistent narrative and language.

## Input → Output
- **In:** the template/collection schema (placeholder names + `max_chars` +
  `lines`), the brief, optional research brief, optional language
- **Out:** `{"deck_title", "theme_preset", "slides": [{"type", "texts":
  {placeholder: str | [str, ...]}}]}`

## Model / settings
- GPT-4o, `temperature=0.6`, JSON mode

## Decision logic
- **Never exceed `max_chars`** (text clips otherwise); front-load key words.
- Placeholders with `lines > 1` take an **array** (one short string per line).
- Fill every placeholder of every slide used.
- Titles punchy; body tight and parallel; one consistent story across slides.
- `generate_deck_content(..., research=True)` first runs Agents 1+2 and grounds
  the copy in the findings.

## Injected guidance
`guides/style.md` (writing/structure) and `guides/color_theme.md` are appended
to the system prompt.

## Safety net (deterministic, downstream)
If generated text still overruns its box, the filler shrinks the font
proportionally (`slide_skills/slide_filler.py` → `shrink_to_fit`) so nothing
overflows the design.
