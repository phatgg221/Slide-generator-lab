# Agent 2 — Web Researcher

**Kind:** agentic (GPT-4o synthesis) + pluggable search backend
**Code:** `slide_skills/research.py` → `web_research(content, keywords)`

## Role
Gather real facts, statistics, definitions, and sources for the keywords, and
return a structured **research brief** the planner and writer can ground on.

## Input → Output
- **In:** `content: str`, `keywords: list[str]`
- **Out:** `ResearchResult(summary: str, method: str, sources: list[{title,url}])`
  - `method` tells you which backend ran.

## How it searches the website (backend priority)
The agent tries backends in order and uses the first available:

1. **Tavily** — if `TAVILY_API_KEY` is set and `tavily-python` is installed.
   - `TavilyClient.search(query=<keywords>, max_results=6, include_answer=True,
     search_depth="advanced")`
   - Takes Tavily's answer + result snippets/URLs as context, then **GPT-4o
     synthesizes** them into the brief (grounded, cites sources by title).
   - `method = "tavily"`, `sources` populated.
2. **OpenAI web_search** (Responses API tool) — `web_search` then
   `web_search_preview`, if the account has the tool. `method = "web_search"`.
3. **Model knowledge** — GPT-4o answers from training, told to avoid invented
   numbers (give ranges / "approximately"). `method = "model-knowledge"`.

So search **never blocks the pipeline** — it degrades gracefully to the next
backend. Per-user keys: resolved via `resolve_tavily_key()` (request override
→ env), so `use_keys(tavily_key=...)` works in a multi-tenant service.

## Decision logic
- Query is the joined keywords (falls back to a content slice if no keywords).
- The synthesis step is instructed to use ONLY supplied results (grounding),
  extract numbers, and write in the content's language.

## Notes
- Tavily search itself is a Tavily credit (not OpenAI tokens); the GPT-4o
  synthesis tokens ARE tracked in the usage counter.
- Enable in the web path with `generate_web_deck(..., research=True)`; the
  `.pptx` `CourseDeckPipeline` runs it via `do_research`.
