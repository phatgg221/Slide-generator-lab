"""Skill 2: GPT-4o writes deck content that fits the template's fill-spec.

Given a TemplateSpec and a user brief ("a pitch deck about X"), asks GPT-4o
for replacement text per text box (respecting character budgets and
paragraph counts) and a DALL-E prompt per picture placeholder. Output is
validated JSON keyed by shape_id, ready for the slide_filler skill.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .config import get_client, TEXT_MODEL
from .template_parser import TemplateSpec

_SYSTEM_PROMPT = """\
You are a presentation copywriter. You will receive:
1. A brief describing the presentation to write.
2. A JSON spec of a slide template: for each slide, the text boxes (with a
   role, the template's current sample text, a max_chars budget, and a
   n_paragraphs count) and the picture placeholders (with aspect ratio).

Write replacement content for every text box and an image-generation prompt
for every picture placeholder.

Rules:
- Stay within each text box's max_chars budget. Going slightly under is good;
  going over breaks the layout. Never exceed it by more than 10%.
- If n_paragraphs > 1 the box is a list: return exactly n_paragraphs lines
  separated by "\\n", one line per list item.
- Match the role: titles are punchy (2-6 words), subtitles one short phrase,
  body text complete but tight, captions a few words.
- Keep a consistent narrative across slides in their given order.
- If the brief supplies specific content — an outline, slide-by-slide notes,
  facts, numbers, names, or exact wording — use it faithfully (verbatim where
  it fits the budget) instead of inventing your own. Only invent content for
  parts of the template the brief doesn't cover.
- If the brief maps content to specific slides (e.g. "slide 3: ..."), respect
  that mapping.
- Image prompts must describe a concrete visual scene (subject, style, mood,
  colors) suited to the slide's content. No text inside images.
- Write in the same language as the brief unless told otherwise.

Return ONLY JSON in this shape (shape_id keys must be strings):
{
  "slides": [
    {
      "index": 0,
      "texts": {"<shape_id>": "replacement text"},
      "images": {"<shape_id>": "DALL-E prompt"}
    }
  ]
}
Include every slide and every shape_id from the spec. Do not invent ids.
"""


@dataclass
class GeneratedSlideContent:
    index: int
    texts: dict[int, str] = field(default_factory=dict)    # shape_id -> text
    images: dict[int, str] = field(default_factory=dict)   # shape_id -> image prompt


@dataclass
class GeneratedDeckContent:
    slides: list[GeneratedSlideContent] = field(default_factory=list)

    def slide(self, index: int) -> GeneratedSlideContent | None:
        return next((s for s in self.slides if s.index == index), None)


def _spec_for_prompt(spec: TemplateSpec) -> dict:
    """Strip layout geometry the model doesn't need; keep what guides writing."""
    return {
        "slides": [
            {
                "index": s.index,
                "texts": [
                    {
                        "shape_id": t.shape_id,
                        "role": t.role,
                        "sample_text": t.current_text,
                        "max_chars": t.max_chars,
                        "n_paragraphs": t.n_paragraphs,
                    }
                    for t in s.texts
                ],
                "images": [
                    {"shape_id": i.shape_id, "aspect_ratio": i.aspect_ratio}
                    for i in s.images
                ],
            }
            for s in spec.slides
        ]
    }


def generate_content(
    spec: TemplateSpec,
    brief: str,
    *,
    language: str | None = None,
    temperature: float = 0.7,
    on_progress: Callable[[int], None] | None = None,
) -> GeneratedDeckContent:
    """Ask GPT-4o for template-fitting content. Returns shape_id-keyed text
    and image prompts for every slide in the spec.

    on_progress, when given, is called with the running character count as
    the response streams in — big templates take a couple of minutes and
    this is the only sign of life."""
    client = get_client()

    user_prompt = f"Brief:\n{brief}\n\nTemplate spec:\n{json.dumps(_spec_for_prompt(spec), ensure_ascii=False)}"
    if language:
        user_prompt += f"\n\nWrite all content in {language}."

    stream = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )
    parts: list[str] = []
    chars = last_report = 0
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if delta:
            parts.append(delta)
            chars += len(delta)
            if on_progress and chars - last_report >= 2000:
                last_report = chars
                on_progress(chars)
    payload = json.loads("".join(parts))

    deck = GeneratedDeckContent()
    valid_ids = {
        s.index: (
            {t.shape_id for t in s.texts},
            {i.shape_id for i in s.images},
        )
        for s in spec.slides
    }
    for raw in payload.get("slides", []):
        idx = raw.get("index")
        if idx not in valid_ids:
            continue
        text_ids, image_ids = valid_ids[idx]
        deck.slides.append(GeneratedSlideContent(
            index=idx,
            texts={
                int(k): str(v)
                for k, v in (raw.get("texts") or {}).items()
                if int(k) in text_ids
            },
            images={
                int(k): str(v)
                for k, v in (raw.get("images") or {}).items()
                if int(k) in image_ids
            },
        ))
    return deck
