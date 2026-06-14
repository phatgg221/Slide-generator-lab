"""Shared OpenAI client + model configuration.

Reads from environment (a local .env is loaded automatically):
    OPENAI_API_KEY        -- required
    OPENAI_TEXT_MODEL     -- default "gpt-4o"
    OPENAI_IMAGE_MODEL    -- default "dall-e-3"
    SLIDE_TEMPLATES_DIR   -- where SVG collections live (default "svg_templates")
    SLIDE_LIBRARY_DIR     -- where .pptx templates live (default "library")
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")


def collections_dir() -> Path:
    """Directory holding SVG template collections. Override with the
    SLIDE_TEMPLATES_DIR env var so an installed package finds your templates
    wherever you keep them."""
    return Path(os.getenv("SLIDE_TEMPLATES_DIR", "svg_templates"))


def library_dir() -> Path:
    """Directory holding .pptx templates. Override with SLIDE_LIBRARY_DIR."""
    return Path(os.getenv("SLIDE_LIBRARY_DIR", "library"))


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or to a "
            ".env file in the project root."
        )
    return OpenAI(api_key=api_key)
