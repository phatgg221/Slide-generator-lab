"""The full multi-agent pipeline:

content -> keywords -> web research -> plan (slides + theme) ->
assemble from library -> GPT-4o content + DALL-E images -> recolor -> deck

    pipeline = CourseDeckPipeline()
    result = pipeline.build(
        course_content="...your course material...",
        library_path="library/slide_library.pptx",
        output_path="out/course_deck.pptx",
    )

Stateless like SlideGeneratorAgent; FastAPI-ready via asyncio.to_thread.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Union

from .agent import SlideGeneratorAgent
from .assembler import build_deck_from_library, load_library_meta
from .planner import plan_deck
from .research import ResearchResult, extract_keywords, web_research
from .template_parser import parse_template
from .theme import PRESETS, apply_palette, auto_map_palette, extract_palette
from .usage import UsageSnapshot, tracker

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    output_path: Path
    keywords: list[str]
    research: ResearchResult | None
    plan: dict
    images_generated: int
    warnings: list[str] = field(default_factory=list)
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)


class CourseDeckPipeline:
    def __init__(
        self,
        *,
        generate_images: bool = True,
        do_research: bool = True,
        image_quality: str = "standard",
        on_progress: Callable[[str], None] | None = None,
    ):
        self.do_research = do_research
        self.on_progress = on_progress or (lambda msg: logger.info(msg))
        self._slide_agent = SlideGeneratorAgent(
            generate_images=generate_images,
            image_quality=image_quality,
            on_progress=self.on_progress,
        )

    def build(
        self,
        course_content: str,
        library_path: Union[str, Path],
        output_path: Union[str, Path],
        *,
        language: str | None = None,
        theme_override: str | None = None,   # preset name; skips planner's choice
    ) -> PipelineResult:
        run_start = tracker.snapshot()

        def stage_usage(label: str, since: UsageSnapshot) -> UsageSnapshot:
            now = tracker.snapshot()
            self.on_progress(f"  [{label} usage] {(now - since).report()}")
            return now

        self.on_progress("Extracting keywords…")
        keywords = extract_keywords(course_content)
        self.on_progress(f"Keywords: {', '.join(keywords)}")
        mark = stage_usage("keywords", run_start)

        research = None
        research_summary = "(no research performed; rely on the course content)"
        if self.do_research:
            self.on_progress("Researching the web…")
            research = web_research(course_content, keywords)
            research_summary = research.summary
            self.on_progress(f"Research done (via {research.method}).")
            mark = stage_usage("research", mark)

        self.on_progress("Planning the deck…")
        library_types, descriptions = load_library_meta(library_path)
        library_spec = parse_template(library_path)
        plan = plan_deck(course_content, research_summary, library_types,
                         library_spec, descriptions=descriptions)
        sequence = [s["type"] for s in plan["slides"]]
        self.on_progress(
            f"Plan: {len(sequence)} slides ({', '.join(sequence)}); "
            f"theme {plan.get('theme') or 'unchanged'}"
        )
        mark = stage_usage("planning", mark)

        with tempfile.TemporaryDirectory() as tmp:
            assembled = Path(tmp) / "assembled.pptx"
            build_deck_from_library(
                library_path, sequence, assembled, library_types=library_types)

            brief = self._compose_brief(course_content, research_summary, plan)
            filled = Path(tmp) / "filled.pptx"
            gen = self._slide_agent.generate(
                assembled, brief, filled, language=language)

            target = self._theme_target(plan, theme_override)
            if target:
                self.on_progress("Applying color theme…")
                mapping = auto_map_palette(extract_palette(filled), target)
                out = apply_palette(filled, mapping, output_path)
            else:
                out = Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(filled.read_bytes())

        total_usage = tracker.snapshot() - run_start
        self.on_progress(f"Done: {out}")
        self.on_progress(f"TOTAL usage: {total_usage.report()}")
        return PipelineResult(
            output_path=out,
            keywords=keywords,
            research=research,
            plan=plan,
            images_generated=gen.images_generated,
            warnings=gen.warnings,
            usage=total_usage,
        )

    @staticmethod
    def _compose_brief(content: str, research: str, plan: dict) -> str:
        lines = [
            f"Deck title: {plan['deck_title']}",
            "",
            "Slide-by-slide plan (follow this mapping exactly):",
        ]
        for i, s in enumerate(plan["slides"]):
            points = "; ".join(s["talking_points"]) or s["topic"]
            lines.append(f"- Slide index {i} ({s['type']}): {s['topic']} — {points}")
        lines += ["", f"Course content:\n{content[:5000]}",
                  "", f"Research brief:\n{research[:4000]}"]
        return "\n".join(lines)

    @staticmethod
    def _theme_target(plan: dict, override: str | None) -> tuple[str, str, str] | None:
        if override:
            return PRESETS[override]
        theme = plan.get("theme") or {}
        if "preset" in theme:
            return PRESETS[theme["preset"]]
        if "colors" in theme:
            c = theme["colors"]
            return (c["primary"], c["secondary"], c["accent"])
        return None
