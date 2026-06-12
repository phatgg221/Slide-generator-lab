# Slide Generator Lab

Agentic Python skills that take a **Canva-exported .pptx template** and fill it
with AI-generated content — text written by **GPT-4o**, images rendered by
**DALL·E 3** — while preserving the template's fonts, colors, layout, bullets,
and image frames.

## How it works

Canva's "Download → Microsoft PowerPoint" export turns each slide into plain
text boxes and pictures. The pipeline is four composable skills:

| Skill | Module | What it does |
|---|---|---|
| `parse_template` | `template_parser.py` | Walks the .pptx, classifies each text box (title/subtitle/body/caption) by font size & position, records char budgets, paragraph counts, and picture aspect ratios. Output is JSON-serializable. |
| `generate_content` | `content_generator.py` | Sends the spec + your brief to GPT-4o (JSON mode). Returns replacement text per text box and a DALL·E prompt per picture, respecting char budgets and bullet counts. |
| `generate_image` | `image_generator.py` | Calls DALL·E 3 at the nearest supported size, then center-crops to the placeholder's exact aspect ratio so nothing distorts. |
| `fill_template` | `slide_filler.py` | Writes text back keeping each paragraph's original formatting (extra bullets are XML-cloned from the last one), and swaps picture bitmaps in place — geometry, crop, and effects untouched. |

`SlideGeneratorAgent` (`agent.py`) chains them: parse → write → render images
in parallel → fill, with progress callbacks and per-shape warnings (e.g. text
over budget, image generation failed).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then paste your OpenAI API key
```

## Usage

```bash
# Inspect what the parser sees in your template (no API key needed)
.venv/bin/python examples/generate_deck.py my_canva_template.pptx --inspect

# Generate a full deck
.venv/bin/python examples/generate_deck.py my_canva_template.pptx \
  "A 5-slide pitch deck for an AI tutoring startup aimed at investors" \
  -o out/deck.pptx

# Skip DALL·E (keep template images), or write in another language
.venv/bin/python examples/generate_deck.py template.pptx "..." --no-images --language Vietnamese
```

Or from Python:

```python
from slide_skills import SlideGeneratorAgent

agent = SlideGeneratorAgent(generate_images=True, image_quality="standard")
result = agent.generate(
    template_path="my_canva_template.pptx",
    brief="A pitch deck about smart farming drones",
    output_path="out/deck.pptx",
)
print(result.output_path, result.warnings)
```

## Using in FastAPI (later)

The skills are blocking (OpenAI sync client), so run them in a thread:

```python
import asyncio, tempfile, uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse
from slide_skills import SlideGeneratorAgent

app = FastAPI()
agent = SlideGeneratorAgent()  # stateless — safe to share across requests

@app.post("/generate")
async def generate(template: UploadFile, brief: str = Form(...)):
    workdir = Path(tempfile.mkdtemp())
    template_path = workdir / "template.pptx"
    template_path.write_bytes(await template.read())
    output_path = workdir / f"deck-{uuid.uuid4().hex[:8]}.pptx"

    result = await asyncio.to_thread(
        agent.generate, template_path, brief, output_path
    )
    return FileResponse(
        result.output_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="deck.pptx",
    )
```

For production: push `agent.generate` to a background worker (Celery/RQ/ARQ)
and poll for the file — a deck with several DALL·E images takes 30–90 s.

## Testing without an API key

```bash
.venv/bin/python tests/test_offline_pipeline.py
```

Builds a fake template, then verifies parsing, format-preserving text
replacement, bullet cloning, and in-place image swapping.

## Notes & limits

- **Char budgets are derived from the template's sample text** — pick a Canva
  template whose sample text resembles your target length. The agent warns
  when GPT-4o exceeds a budget by >25%.
- Pictures placed by Canva as *slide backgrounds* (XML background fills, not
  picture shapes) are not detected; regular image placeholders are.
- Grouped shapes are skipped; ungroup decorative groups in Canva before
  exporting if their text should be replaced.
- DALL·E 3 renders 1024×1024, 1792×1024, or 1024×1792; the skill crops to the
  placeholder aspect, so extreme aspect ratios (very wide banners) lose more
  of the image to the crop.
