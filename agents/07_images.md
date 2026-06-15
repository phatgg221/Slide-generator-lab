# Agent 7 — Image Generator

**Kind:** agentic (image/vector generation) — optional
**Code:** `slide_skills/image_generator.py` → `generate_image`;
`slide_skills/svg_image_generator.py` → `generate_svg_image`

## Role
Produce an image for each image placeholder, sized to the slot's aspect ratio.

## Two backends
1. **AI photo** — `generate_image(prompt, aspect_ratio, quality)`
   - Auto-detects the account's model: tries `gpt-image-1` → `gpt-image-1-mini`
     → `dall-e-3` → `dall-e-2`, remembers the first that works.
   - Adapts size + parameters per model family; center-crops to the exact
     aspect ratio. ~$0.04–0.25/image.
2. **SVG vector** — `generate_svg_image(prompt, aspect_ratio, palette=…)`
   - GPT-4o writes a flat **abstract** SVG illustration; rasterized locally
     (resvg). ~$0.005/image, illustration style (not photoreal).

## Input → Output
- **In:** a prompt (written by the planner/writer per image slot) + aspect ratio
- **Out:** PNG bytes, cropped to fit the placeholder

## Decision logic / prompts
- The prompt describes a concrete scene (subject, style, mood, colors), no text
  in the image.
- For SVG, the system prompt steers toward abstract geometric compositions in
  the deck's palette (literal object drawings look clumsy).

## Notes
- Optional: skip entirely (`generate_images=False`) or choose the source
  (`image_source="svg"` for the cheap vector path).
- Image cost is priced into the usage counter per call.
