"""Shared OpenAI client + model configuration.

Reads from environment (a local .env is loaded automatically):
    OPENAI_API_KEY      -- required
    OPENAI_TEXT_MODEL   -- default "gpt-4o"
    OPENAI_IMAGE_MODEL  -- default "dall-e-3"
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or to a "
            ".env file in the project root."
        )
    return OpenAI(api_key=api_key)
