"""Shared OpenAI client + model configuration.

Reads from environment (a local .env is loaded automatically):
    OPENAI_API_KEY        -- required
    OPENAI_TEXT_MODEL     -- default "gpt-4o"
    OPENAI_IMAGE_MODEL    -- default "dall-e-3"
    TAVILY_API_KEY        -- optional; enables Tavily web search in research.py
    SLIDE_TEMPLATES_DIR   -- where SVG collections live (default "svg_templates")
    SLIDE_LIBRARY_DIR     -- where .pptx templates live (default "library")

Per-request keys (multi-user services): wrap calls in `use_keys(...)` so each
request/async task uses its own OpenAI + Tavily key, safely under concurrency:

    from slide_skills.config import use_keys
    with use_keys(openai_key=user_openai, tavily_key=user_tavily):
        generate_web_deck(...)

Outside a `use_keys` block, keys fall back to the environment.
"""

from __future__ import annotations

import contextvars
import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")

# Per-request key overrides (async-task-local — safe under FastAPI concurrency)
_openai_key_var: contextvars.ContextVar = contextvars.ContextVar("openai_key", default=None)
_tavily_key_var: contextvars.ContextVar = contextvars.ContextVar("tavily_key", default=None)


@contextmanager
def use_keys(openai_key: str | None = None, tavily_key: str | None = None):
    """Scope OpenAI/Tavily keys to this block (and any async task started in
    it). Use one per request in a multi-tenant service so users' keys never
    leak across requests."""
    tok_o = _openai_key_var.set(openai_key) if openai_key else None
    tok_t = _tavily_key_var.set(tavily_key) if tavily_key else None
    try:
        yield
    finally:
        if tok_o is not None:
            _openai_key_var.reset(tok_o)
        if tok_t is not None:
            _tavily_key_var.reset(tok_t)


def resolve_openai_key() -> str | None:
    return _openai_key_var.get() or os.getenv("OPENAI_API_KEY")


def resolve_tavily_key() -> str | None:
    return _tavily_key_var.get() or os.getenv("TAVILY_API_KEY")


def collections_dir() -> Path:
    """Directory holding SVG template collections. Override with the
    SLIDE_TEMPLATES_DIR env var so an installed package finds your templates
    wherever you keep them."""
    return Path(os.getenv("SLIDE_TEMPLATES_DIR", "svg_templates"))


def library_dir() -> Path:
    """Directory holding .pptx templates. Override with SLIDE_LIBRARY_DIR."""
    return Path(os.getenv("SLIDE_LIBRARY_DIR", "library"))


def _guides_dir() -> Path:
    """Directory holding markdown guidance injected into agent prompts.
    Override with SLIDE_GUIDES_DIR (e.g. a per-brand guide set)."""
    return Path(os.getenv("SLIDE_GUIDES_DIR", "guides"))


def load_guide(name: str) -> str:
    """Read a guidance markdown file (e.g. 'color_theme', 'style') to inject
    into an agent's system prompt. Returns '' if absent (guides are optional).

    Resolution order:
      1. SLIDE_GUIDES_DIR / <name>.md   — your override (per-brand taste)
      2. packaged slide_skills/guides/<name>.md — ships with the library, so a
         bare `pip install` already has sensible defaults.
    Re-read each call so edits take effect live."""
    for base in (_guides_dir(), Path(__file__).resolve().parent / "guides"):
        try:
            text = (base / f"{name}.md").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return f"\n\n--- {name} guidance ---\n{text}\n--- end guidance ---\n"
    return ""


@lru_cache(maxsize=16)
def _client_for(api_key: str) -> OpenAI:
    """One cached client per distinct key (small pool) — so concurrent users
    with different keys each get the right client, without rebuilding it on
    every call."""
    return OpenAI(api_key=api_key)


def get_client() -> OpenAI:
    api_key = resolve_openai_key()
    if not api_key:
        raise RuntimeError(
            "No OpenAI API key. Set OPENAI_API_KEY in the environment / .env, "
            "or wrap the call in use_keys(openai_key=...)."
        )
    return _client_for(api_key)
