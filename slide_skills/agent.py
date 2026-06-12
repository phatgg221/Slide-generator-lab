"""Orchestrator: chains the four skills into one template -> deck pipeline.

    agent = SlideGeneratorAgent()
    result = agent.generate(
        template_path="canva_template.pptx",
        brief="A 5-slide pitch for an AI tutoring startup",
        output_path="out/deck.pptx",
    )

Designed to be called from FastAPI: the class is stateless between calls, so
one instance can serve concurrent requests (run it via asyncio.to_thread or
a thread pool — the OpenAI calls are blocking).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Union

from .content_generator import GeneratedDeckContent, generate_content
from .image_generator import generate_image
from .slide_filler import fill_template
from .template_parser import TemplateSpec, parse_template

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    output_path: Path
    spec: TemplateSpec
    content: GeneratedDeckContent
    images_generated: int = 0
    warnings: list[str] = field(default_factory=list)


class SlideGeneratorAgent:
    """template.pptx + brief -> filled deck.pptx"""

    def __init__(
        self,
        *,
        generate_images: bool = True,
        image_quality: str = "standard",
        max_image_workers: int = 3,
        on_progress: Callable[[str], None] | None = None,
    ):
        self.generate_images = generate_images
        self.image_quality = image_quality
        self.max_image_workers = max_image_workers
        self.on_progress = on_progress or (lambda msg: logger.info(msg))

    def generate(
        self,
        template_path: Union[str, Path],
        brief: str,
        output_path: Union[str, Path],
        *,
        language: str | None = None,
    ) -> GenerationResult:
        self.on_progress("Parsing template…")
        spec = parse_template(template_path)

        n_texts = sum(len(s.texts) for s in spec.slides)
        n_images = sum(len(s.images) for s in spec.slides)
        self.on_progress(
            f"Found {len(spec.slides)} slides, {n_texts} text boxes, {n_images} pictures."
        )

        self.on_progress("Writing content with GPT-4o (1-3 min for big decks)…")
        content = generate_content(
            spec, brief, language=language,
            on_progress=lambda n: self.on_progress(f"  …still writing ({n:,} chars so far)"),
        )

        warnings = self._check_budgets(spec, content)

        images: dict[tuple[int, int], bytes] = {}
        if self.generate_images and n_images:
            self.on_progress(f"Rendering {n_images} images with DALL-E…")
            images = self._render_images(spec, content, warnings)

        self.on_progress("Filling template…")
        out = fill_template(template_path, content, output_path, images=images)
        self.on_progress(f"Done: {out}")

        return GenerationResult(
            output_path=out,
            spec=spec,
            content=content,
            images_generated=len(images),
            warnings=warnings,
        )

    def _check_budgets(
        self, spec: TemplateSpec, content: GeneratedDeckContent
    ) -> list[str]:
        warnings = []
        for slide_spec in spec.slides:
            slide_content = content.slide(slide_spec.index)
            if slide_content is None:
                warnings.append(f"Slide {slide_spec.index}: no content generated.")
                continue
            for t in slide_spec.texts:
                text = slide_content.texts.get(t.shape_id)
                if text is None:
                    warnings.append(
                        f"Slide {slide_spec.index}, shape {t.shape_id} ({t.role}): "
                        "no text generated, template text kept."
                    )
                elif len(text) > t.max_chars * 1.25:
                    warnings.append(
                        f"Slide {slide_spec.index}, shape {t.shape_id} ({t.role}): "
                        f"text is {len(text)} chars vs budget {t.max_chars} — may overflow."
                    )
        return warnings

    def _render_images(
        self,
        spec: TemplateSpec,
        content: GeneratedDeckContent,
        warnings: list[str],
    ) -> dict[tuple[int, int], bytes]:
        jobs = []  # (slide_index, shape_id, prompt, aspect_ratio)
        for slide_spec in spec.slides:
            slide_content = content.slide(slide_spec.index)
            if slide_content is None:
                continue
            for img in slide_spec.images:
                prompt = slide_content.images.get(img.shape_id)
                if prompt:
                    jobs.append((slide_spec.index, img.shape_id, prompt, img.aspect_ratio))

        results: dict[tuple[int, int], bytes] = {}

        def render(job):
            idx, shape_id, prompt, aspect = job
            return (idx, shape_id), generate_image(
                prompt, aspect, quality=self.image_quality
            )

        with ThreadPoolExecutor(max_workers=self.max_image_workers) as pool:
            for job, future in [(j, pool.submit(render, j)) for j in jobs]:
                try:
                    key, png = future.result()
                    results[key] = png
                except Exception as exc:  # keep the deck usable on partial failure
                    warnings.append(
                        f"Slide {job[0]}, picture {job[1]}: image generation failed "
                        f"({exc}); template image kept."
                    )
        return results
