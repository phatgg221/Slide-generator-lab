"""Skill 7: planner agent — decides the deck's shape before any writing.

Given course content + research + the slide library, GPT-4o decides:
  - how many slides and which library slide types, in what order
  - what each slide should cover (topic + talking points)
  - the color theme (a named preset or three custom colors)

The plan is plain JSON so it can be reviewed/edited before assembly.
"""

from __future__ import annotations

import json
import re

from .config import get_client, TEXT_MODEL
from .template_parser import TemplateSpec
from .theme import PRESETS
from .usage import tracker

# What each library slide type is for. Used both in the planner prompt and
# in the docs given to the user preparing the Canva library.
SLIDE_TYPE_DESCRIPTIONS = {
    "title":      "Opening slide: course/topic title, subtitle, presenter name",
    "agenda":     "Table of contents listing the main sections",
    "section":    "Section divider: big heading announcing a new part",
    "concept":    "Explain one concept: heading, definition/explanation, supporting image",
    "bullets":    "Key points as a 3-5 item list with a heading",
    "statistic":  "Big number callouts: 2-3 statistics with labels",
    "graph":      "Visual/diagram area with an insight caption",
    "comparison": "Two-column comparison: A vs B with points under each",
    "quote":      "One key quote or highlighted statement with attribution",
    "summary":    "Recap of takeaways and closing",
}

MIN_SLIDES, MAX_SLIDES = 3, 20


def plan_deck(
    content: str,
    research_summary: str,
    library_types: list[str],
    library_spec: TemplateSpec,
    *,
    descriptions: dict[str, str] | None = None,
    temperature: float = 0.5,
) -> dict:
    """Return {"deck_title", "theme", "slides": [{"type", "topic",
    "talking_points"}]} using only slide types present in the library.
    Types starting with "_" are never offered to the planner."""
    client = get_client()
    descriptions = descriptions or {}

    capacity = []
    for slide_type, slide in zip(library_types, library_spec.slides):
        if slide_type.startswith("_"):
            continue
        capacity.append({
            "type": slide_type,
            "purpose": descriptions.get(slide_type)
                       or SLIDE_TYPE_DESCRIPTIONS.get(slide_type, ""),
            "text_boxes": len(slide.texts),
            "images": len(slide.images),
        })

    system = (
        "You are a presentation planner. Given course content and research, "
        "design a slide deck using ONLY the available slide types. Types may "
        "be reused (e.g. several 'concept' slides).\n"
        "Rules:\n"
        f"- Between {MIN_SLIDES} and {MAX_SLIDES} slides; match depth to the content.\n"
        "- Start with 'title', end with 'summary' when those types exist.\n"
        "- Use 'statistic' or 'graph' only where the research has real numbers.\n"
        "- Pick a theme that fits the topic's mood: either one preset name "
        f"from {sorted(PRESETS)} or three custom hex colors.\n"
        "Return ONLY JSON:\n"
        '{"deck_title": "...",\n'
        ' "theme": {"preset": "name"} OR {"colors": {"primary": "RRGGBB", '
        '"secondary": "RRGGBB", "accent": "RRGGBB"}},\n'
        ' "slides": [{"type": "...", "topic": "...", '
        '"talking_points": ["...", "..."]}]}'
    )
    user = (
        f"Available slide types:\n{json.dumps(capacity, ensure_ascii=False)}\n\n"
        f"Course content:\n{content[:6000]}\n\n"
        f"Research brief:\n{research_summary[:4000]}"
    )

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    tracker.record_chat(response.usage)
    plan = json.loads(response.choices[0].message.content)
    return _validate_plan(plan, library_types)


def _validate_plan(plan: dict, library_types: list[str]) -> dict:
    valid_types = {t for t in library_types if not t.startswith("_")}
    slides = [s for s in plan.get("slides", [])
              if isinstance(s, dict) and s.get("type") in valid_types]
    if not slides:
        raise ValueError(f"Planner produced no usable slides: {plan}")
    slides = slides[:MAX_SLIDES]

    theme = plan.get("theme") or {}
    if "preset" in theme and theme["preset"] not in PRESETS:
        theme = {}
    if "colors" in theme:
        colors = {k: str(v).upper().lstrip("#") for k, v in theme["colors"].items()}
        if all(re.fullmatch(r"[0-9A-F]{6}", colors.get(k, ""))
               for k in ("primary", "secondary", "accent")):
            theme = {"colors": colors}
        else:
            theme = {}

    return {
        "deck_title": str(plan.get("deck_title", "")),
        "theme": theme,
        "slides": [{
            "type": s["type"],
            "topic": str(s.get("topic", "")),
            "talking_points": [str(p) for p in s.get("talking_points", [])],
        } for s in slides],
    }
