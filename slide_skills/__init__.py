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

__version__ = "0.2.12"

from .template_parser import parse_template, TemplateSpec, SlideSpec, TextElement, ImageElement
from .content_generator import generate_content, GeneratedDeckContent
from .image_generator import generate_image
from .svg_image_generator import generate_svg_image, generate_svg_markup
from .slide_filler import fill_template
from .theme import extract_palette, auto_map_palette, propose_palette, apply_palette, PRESETS
from .research import extract_keywords, web_research, ResearchResult
from .planner import plan_deck, SLIDE_TYPE_DESCRIPTIONS
from .assembler import build_deck_from_library, load_library_types, DEFAULT_LIBRARY_TYPES
from .agent import SlideGeneratorAgent
from .pipeline import CourseDeckPipeline
from .usage import tracker as usage_tracker, UsageSnapshot
from .config import use_keys
from .transitions import apply_transitions, EFFECTS as TRANSITION_EFFECTS
from .animations import add_animations, ENTRANCE_EFFECTS
from .template_maker import clean_template, auto_manifest, prepare_template, list_templates
from .merge_template import (
    make_placeholder_template, render_placeholders, generate_merge_data, load_schema,
)
from .svg_template_maker import make_svg_templates
from .svg_slide_renderer import render_svg_slide, render_svg_deck
from .svg_collections import (
    scan_collection, list_collections, import_collection, fill_svg, retheme_svg,
    generate_deck_content, generate_web_deck,
)
from .html_deck import build_html_deck
from .svg_categories import (
    scan_template_library, shortlist_variants, select_and_fill_slide,
    generate_deck_from_plan,
)
from .document_deck import (
    parse_document, map_document_to_plan, generate_deck_from_document,
)

__all__ = [
    "parse_template",
    "TemplateSpec",
    "SlideSpec",
    "TextElement",
    "ImageElement",
    "generate_content",
    "GeneratedDeckContent",
    "generate_image",
    "generate_svg_image",
    "generate_svg_markup",
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
    "use_keys",
    "apply_transitions",
    "TRANSITION_EFFECTS",
    "add_animations",
    "ENTRANCE_EFFECTS",
    "clean_template",
    "auto_manifest",
    "prepare_template",
    "list_templates",
    "make_placeholder_template",
    "render_placeholders",
    "generate_merge_data",
    "load_schema",
    "make_svg_templates",
    "render_svg_slide",
    "render_svg_deck",
    "scan_collection",
    "list_collections",
    "import_collection",
    "fill_svg",
    "retheme_svg",
    "generate_deck_content",
    "generate_web_deck",
    "build_html_deck",
    "scan_template_library",
    "shortlist_variants",
    "select_and_fill_slide",
    "generate_deck_from_plan",
    "parse_document",
    "map_document_to_plan",
    "generate_deck_from_document",
]
