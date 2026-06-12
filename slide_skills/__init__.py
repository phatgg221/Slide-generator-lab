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
from .agent import SlideGeneratorAgent

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
    "SlideGeneratorAgent",
]
