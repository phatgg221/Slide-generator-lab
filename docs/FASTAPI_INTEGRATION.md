# Integrating `slide-skills` into a FastAPI app

A phased plan to wrap the published `slide-skills` library in a FastAPI
service. The library owns all deck logic — the service only handles HTTP,
jobs, storage, and config.

---

## Phase 0 — Project setup

```
your-fastapi-app/
  app/
    main.py            # FastAPI app + routes
    deps.py            # config, paths, settings
    jobs.py            # background generation worker
    schemas.py         # pydantic request/response models
  templates/           # SVG collections / categories  (or mount a volume)
  storage/             # generated decks (or use S3)
  .env
  requirements.txt
```

```bash
pip install "slide-skills>=0.2.2" fastapi uvicorn python-multipart
# add a job queue when needed: pip install "arq" (or celery/rq)
```

`.env`:
```
OPENAI_API_KEY=sk-...
SLIDE_TEMPLATES_DIR=/abs/path/to/templates
SLIDE_LIBRARY_DIR=/abs/path/to/pptx_library     # only if using the .pptx path
```

---

## Phase 1 — Read-only endpoints (no AI, fast)

Expose what templates exist so the frontend can offer choices.

```python
# app/main.py
from fastapi import FastAPI
from slide_skills import scan_template_library, list_collections

app = FastAPI()

@app.get("/templates/categories")
def categories():
    return scan_template_library(None).category_map()   # uses SLIDE_TEMPLATES_DIR

@app.get("/templates/collections")
def collections():
    return list_collections()                            # uses SLIDE_TEMPLATES_DIR
```
Ship this first — it validates that the templates dir is wired correctly and
needs no API key.

---

## Phase 2 — Synchronous generation (MVP)

Good enough while decks are small / few images. Generation is **blocking**, so
run it in a thread to keep the event loop free.

```python
import asyncio, uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from slide_skills import generate_web_deck

STORAGE = Path("storage"); STORAGE.mkdir(exist_ok=True)

class GenReq(BaseModel):
    topic: str
    collection: str = "starter"
    palette: str | None = "auto"
    language: str | None = None
    animation: str = "rise"

@app.post("/generate")
async def generate(req: GenReq):
    deck_id = uuid.uuid4().hex[:8]
    out = STORAGE / f"{deck_id}.html"
    result = await asyncio.to_thread(
        generate_web_deck, req.collection, req.topic, str(out),
        palette=req.palette, language=req.language, animation=req.animation,
    )
    return {"deck_id": deck_id, "slides": result["slides"], "usage": result["usage"]}

@app.get("/decks/{deck_id}")
def get_deck(deck_id: str):
    return FileResponse(STORAGE / f"{deck_id}.html", media_type="text/html")
```
The `usage` block (tokens + `estimated_cost_usd`) comes straight from the
library — return/log it for billing.

---

## Phase 3 — Background jobs (production)

Image-heavy decks take 30s–3min — too long for one HTTP request. Move
generation to a worker and let the client poll.

- Pattern: `POST /generate` enqueues a job → returns `{job_id, status:"queued"}`;
  `GET /jobs/{job_id}` returns `status` (`queued|running|done|error`), and on
  done the `deck_id` + `usage`.
- Use ARQ (async-native) or Celery/RQ. The worker calls the same
  `generate_web_deck(...)` synchronously (no thread needed inside the worker).
- Store job state in Redis or your DB.

```python
# jobs.py (ARQ worker task)
from slide_skills import generate_web_deck
async def run_generation(ctx, deck_id, **kwargs):
    out = f"storage/{deck_id}.html"
    return generate_web_deck(output_path=out, **kwargs)   # returns dict incl. usage
```

---

## Phase 4 — Plan-driven + variant selection (optional, richer)

If the frontend builds a plan (category per slide, like the layout dropdown),
use the category library + variant-selecting agent instead of a single
collection.

```python
from slide_skills import generate_deck_from_plan

@app.post("/generate-from-plan")
async def generate_from_plan(plan: dict):       # {"title","slides":[{"category",...}]}
    out = f"storage/{uuid.uuid4().hex[:8]}.html"
    result = await asyncio.to_thread(
        generate_deck_from_plan, plan, "templates", out, palette="auto")
    return {"slides": result["slides"], "warnings": result["warnings"],
            "usage": result["usage"]}
```

---

## Phase 5 — Template management (optional)

Let operators/users add collections without redeploying.

```python
from fastapi import UploadFile
from slide_skills import import_collection
# accept a zip of .svg files, unzip to a temp dir, then:
#   import_collection(temp_dir, name)   -> copies into SLIDE_TEMPLATES_DIR + validates
```
`import_collection` raises if no `{{placeholders}}` are found (i.e. the SVG was
exported with outlined text) — surface that as a 400.

---

## Cross-cutting concerns

- **Secrets**: `OPENAI_API_KEY` from env/secret manager, never in code.
- **Templates on the server**: mount a volume or sync from a private git
  repo / S3 to `SLIDE_TEMPLATES_DIR`. Keep them out of the code image so
  designs update independently of deploys.
- **Cost control**: read `result["usage"]["estimated_cost_usd"]` per request;
  enforce per-user budgets / rate limits; log totals.
- **Output storage**: local dir is fine for one box; use S3 + presigned URLs
  for multi-instance. HTML decks are single self-contained files.
- **Concurrency**: each generation makes several OpenAI calls; cap concurrent
  jobs (worker pool size) to avoid rate-limit errors.
- **CORS**: enable if the frontend is a separate origin embedding the deck via
  `<iframe>`.

## Decisions to confirm before building
1. Sync (Phase 2) or job queue (Phase 3)? Depends on whether decks use images.
2. Single collection (`/generate`) or plan-driven (`/generate-from-plan`)?
3. Output storage: local disk vs S3?
4. Auth / per-user accounting needed?
```
