# Agent 1 — Keyword Extractor

**Kind:** agentic (GPT-4o)
**Code:** `slide_skills/research.py` → `extract_keywords(content, max_keywords=10)`

## Role
Pull the core topics out of the raw input (a brief or longer course content) so
the researcher has focused search terms.

## Input → Output
- **In:** `content: str` (truncated to 8000 chars), `max_keywords` (default 10)
- **Out:** `list[str]` — keywords, most important first, in the content's language

## Model / settings
- GPT-4o, `temperature=0.2` (deterministic-ish), JSON mode
- Returns `{"keywords": [...]}`; the agent trims to `max_keywords`

## Decision logic
The model judges which terms matter most for *researching* the topic — proper
nouns, domain terms, named entities — not stopwords or filler. Language is
preserved (Vietnamese in → Vietnamese keywords).

## Notes
- Cheap (~hundreds of tokens). Usage is tracked.
- Only runs when research is enabled. If you skip research, this is skipped too.
