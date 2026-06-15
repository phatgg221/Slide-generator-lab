# Agent cards

One card per step in the generation pipeline. Each card documents what the
agent does, its input/output, the model or backend it uses, and its decision
logic. Cards marked **agentic** make an LLM decision; cards marked
**deterministic** are pure code (no LLM).

The orchestration (which steps run, in what order) is a deterministic harness
(`pipeline.py`, `generate_web_deck`, `generate_deck_from_plan`) — see the flow
diagram in the main README.

| # | Agent | File | Kind |
|---|---|---|---|
| 1 | Keyword extractor | [01_keywords.md](01_keywords.md) | agentic |
| 2 | Web researcher | [02_research.md](02_research.md) | agentic + search backends |
| 3 | Deck planner | [03_planner.md](03_planner.md) | agentic |
| 4 | Category→variant mapper | [04_variant_mapper.md](04_variant_mapper.md) | agentic + schema-fit |
| 5 | Content writer | [05_writer.md](05_writer.md) | agentic |
| 6 | Theme / palette | [06_theme.md](06_theme.md) | agentic + deterministic |
| 7 | Image generator | [07_images.md](07_images.md) | agentic |
| 8 | Assembler | [08_assembler.md](08_assembler.md) | deterministic |

Two markdown guides tune the agents' taste at runtime (injected into prompts):
`guides/color_theme.md` and `guides/style.md` (override dir: `SLIDE_GUIDES_DIR`).
