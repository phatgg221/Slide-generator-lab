"""Offline tests for OpenRouter provider resolution and client wrapping."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import slide_skills.config as cfg


class _FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs.copy())
        return kwargs


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.chat = type("Chat", (), {})()
        self.chat.completions = _FakeCompletions()
        self.images = type("Images", (), {"generate": lambda self, **kwargs: kwargs})()


def _reset_env():
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("OPENROUTER_API_KEY", None)
    cfg._openai_key_var.set(None)
    cfg._openrouter_key_var.set(None)
    cfg._clients.clear()


def test_openrouter_provider_and_prefixing():
    _reset_env()
    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    cfg.OpenAI = _FakeClient

    key, base_url = cfg._resolve_provider()
    assert key == "sk-or-test"
    assert base_url == cfg.OPENROUTER_BASE_URL

    client = cfg.get_client()
    response = client.chat.completions.create(model=cfg.TEXT_MODEL, messages=[])
    assert response["model"] == "openai/gpt-4o"
    assert client.chat.completions.calls[0]["model"] == "openai/gpt-4o"


def test_use_keys_openrouter_overrides_env():
    _reset_env()
    os.environ["OPENROUTER_API_KEY"] = "sk-or-env"
    cfg.OpenAI = _FakeClient

    with cfg.use_keys(openrouter_key="sk-or-local"):
        key, base_url = cfg._resolve_provider()
        assert key == "sk-or-local"
        assert base_url == cfg.OPENROUTER_BASE_URL


def test_openai_env_wins_native_path():
    _reset_env()
    os.environ["OPENAI_API_KEY"] = "sk-openai"
    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    cfg.OpenAI = _FakeClient

    key, base_url = cfg._resolve_provider()
    assert key == "sk-openai"
    assert base_url is None


if __name__ == "__main__":
    test_openrouter_provider_and_prefixing()
    test_use_keys_openrouter_overrides_env()
    test_openai_env_wins_native_path()
    print("✓ OpenRouter support tests passed")