# Build brief: FastAPI service on top of the `slide-skills` library

A self-contained spec for building a web service that wraps the `slide-skills`
package. Assumes no prior context. Do **not** reimplement deck logic — wrap the
library.

## What the library does
Generates AI slide decks (animated self-contained HTML, optionally PowerPoint)
by filling **templates** (folders of live-text SVGs) with AI-written content,
re-theming colors, and assembling a deck. Templates live on disk, not in the
package.

- Install: `pip install slide-skills` — https://pypi.org/project/slide-skills/
- Source: https://github.com/phatgg221/Slide-generator-lab

## Required configuration (env vars)
```
OPENAI_API_KEY=sk-...                 # REQUIRED — all AI calls fail without it
SLIDE_TEMPLATES_DIR=/srv/templates    # where SVG collections + category folders live
SLIDE_LIBRARY_DIR=/srv/pptx_library   # optional, for the .pptx path
OPENAI_TEXT_MODEL=gpt-4o              # optional
OPENAI_IMAGE_MODEL=gpt-image-1        # optional
```

## Library API to wrap (import from `slide_skills`)
```python
# Discover available templates (for UI dropdowns)
list_collections(base_dir=None) -> list[dict]
scan_template_library(base_dir) -> TemplateLibrary
#   .category_map() -> [{category, purpose, variants:[{name, description}]}]

# Generate from a free-text topic (library plans the slides itself)
generate_web_deck(collection, brief, output_path, *,
                  palette="auto", language=None, animation="rise") -> dict
#   -> {"output_path", "deck_title", "slides", "theme", "usage"}

# Generate from a structured plan (caller names a category per slide;
# an agent picks the best design variant per slide)
generate_deck_from_plan(plan, library_dir, output_path, *,
                        palette=None, language=None, animation="rise", title=None) -> dict
#   plan = {"title": str, "slides": [{"category": str, "topic"/"talking_points": ...}]}
#   -> {"output_path", "slides", "warnings", "usage"}

# Add a template collection at runtime (e.g. user uploads a Figma SVG export)
import_collection(src_folder, name, *, overwrite=False) -> dict
```
- `palette`: `"auto"` (AI picks), preset name (`teal`, `forest`, `midnight`, …),
  RGB tuple, or `None` (keep template colors).
- `animation`: `rise | fade | scale | none`.

### Token usage / cost — returned per call
Every `generate_*` result includes a `usage` block for that run:
```python
result["usage"] = {
  "input_tokens": int, "output_tokens": int, "total_tokens": int,
  "requests": int, "estimated_cost_usd": float, "report": str,
}
```
Surface this in API responses, log it per request, and use it for billing /
rate limits. (A library-wide tracker also exists: `from slide_skills import
usage_tracker; usage_tracker.snapshot()`.)

## Endpoints to build
- `GET  /templates` → `scan_template_library(...).category_map()` (+ `list_collections`)
- `POST /generate` → `{topic, collection, palette?, language?, animation?}` →
  `generate_web_deck` → return HTML (FileResponse) or a job id; include `usage`.
- `POST /generate-from-plan` → body is the `plan` dict → `generate_deck_from_plan`.
- `POST /collections` → multipart upload of an SVG folder/zip → `import_collection`.
- `GET  /decks/{id}` → serve a generated `deck.html`.
- (optional) `GET /usage` → aggregate cost per user/key.

## Critical implementation notes
1. **Generate calls are blocking** (sync OpenAI calls). In async FastAPI run via
   `await asyncio.to_thread(generate_web_deck, ...)`. Image-heavy decks take
   30s–3min → use a **job queue** (Celery/RQ/ARQ) + poll endpoint, not a
   blocking request.
2. **Output**: write to a per-request working dir; serve with
   `FileResponse(media_type="text/html")`. HTML decks are self-contained.
3. **Templates on the server**: deploy separately (private git repo or S3 synced
   to `SLIDE_TEMPLATES_DIR`); do not bundle into the code image.
4. **Secrets**: `OPENAI_API_KEY` from a secret manager, never in code.
5. **Cost guardrails**: read `result["usage"]["estimated_cost_usd"]` per request;
   enforce per-user budgets/rate limits.

## Out of scope / constraints
- The library owns deck logic — wrap, don't reimplement.
- Charts render as designed art, not data-driven.
- `.pptx`→SVG conversion (`svg_template_maker`) needs LibreOffice on the host;
  the web/SVG path does not.
