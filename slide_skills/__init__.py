"""Agentic skills for filling Canva-exported .pptx templates with AI content.

Each skill is a standalone, importable function/class so the package can be
wired into a FastAPI app, a CLI, or an agent loop without modification.

Skills:
    parse_template      -- inspect a .pptx and produce a fill-spec (what can be replaced)
    generate_content    -- GPT-4o writes text + image prompts that fit the spec
    generate_image      -- DALL-E renders an image sized for a placeholder
    fill_template       -- write generated content back into the .pptx
    SlideGeneratorAgent -- orchestrates the four skills end to end
"""

from .template_parser import parse_template, TemplateSpec, SlideSpec, TextElement, ImageElement
from .content_generator import generate_content, GeneratedDeckContent
from .image_generator import generate_image
from .slide_filler import fill_template
from .theme import extract_palette, auto_map_palette, propose_palette, apply_palette, PRESETS
from .research import extract_keywords, web_research, ResearchResult
from .planner import plan_deck, SLIDE_TYPE_DESCRIPTIONS
from .assembler import build_deck_from_library, load_library_types, DEFAULT_LIBRARY_TYPES
from .agent import SlideGeneratorAgent
from .pipeline import CourseDeckPipeline
from .usage import tracker as usage_tracker, UsageSnapshot

__all__ = [
    "parse_template",
    "TemplateSpec",
    "SlideSpec",
    "TextElement",
    "ImageElement",
    "generate_content",
    "GeneratedDeckContent",
    "generate_image",
    "fill_template",
    "extract_palette",
    "auto_map_palette",
    "propose_palette",
    "apply_palette",
    "PRESETS",
    "extract_keywords",
    "web_research",
    "ResearchResult",
    "plan_deck",
    "SLIDE_TYPE_DESCRIPTIONS",
    "build_deck_from_library",
    "load_library_types",
    "DEFAULT_LIBRARY_TYPES",
    "SlideGeneratorAgent",
    "CourseDeckPipeline",
    "usage_tracker",
    "UsageSnapshot",
]
