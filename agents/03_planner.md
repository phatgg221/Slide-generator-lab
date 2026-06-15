# Agent 3 — Deck Planner

**Kind:** agentic (GPT-4o)
**Code:** `slide_skills/planner.py` → `plan_deck(content, research_summary,
library_types, library_spec, descriptions=…)`

## Role
Decide the **shape** of the deck before any writing: how many slides, which
slide types (from what the template actually offers), in what order, and the
color theme.

## Input → Output
- **In:** content, research brief, the available `library_types` + their
  descriptions, and the template spec (text-box/image counts per type)
- **Out:**
  ```json
  {"deck_title": "...",
   "theme": {"preset": "teal"} | {"colors": {"primary","secondary","accent"}},
   "slides": [{"type": "...", "topic": "...", "talking_points": ["...", ...]}]}
  ```

## Model / settings
- GPT-4o, `temperature=0.5`, JSON mode
- Output is validated: only known types kept, slide count clamped to
  `[MIN_SLIDES, MAX_SLIDES]`, theme normalized (unknown preset → dropped).

## Decision logic
- Uses ONLY slide types present in the library (types may repeat).
- Starts with `title`, ends with `summary`/`closing` when present.
- Uses stat/chart types only when the research has real numbers.
- Picks a theme that fits the topic's mood (a preset or 3 custom hex colors).
- Types starting with `_` are hidden from the planner (skip slides).

## Injected guidance (editable)
`guides/style.md` (structure, layout choice) and `guides/color_theme.md`
(palette principles) are appended to the system prompt — edit them to change
the planner's taste without code changes.

## Notes
- This is the planner for the **collection / pptx** paths. In the **category**
  path, the *caller* supplies the plan (which names categories) and Agent 4
  picks the variant instead.
