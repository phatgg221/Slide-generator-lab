"""Token/cost tracking across every OpenAI call the skills make.

All skills report into a process-wide tracker (thread-safe — DALL-E calls
run in threads). Take a snapshot before a job and subtract after to get
that job's usage:

    from slide_skills.usage import tracker
    before = tracker.snapshot()
    ...run pipeline...
    print((tracker.snapshot() - before).report())

Cost estimates use the price table below (USD, may drift from OpenAI's
current pricing — update _PRICES if your bill disagrees).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

# USD per 1M tokens / per image. Last checked: mid-2026.
_PRICES = {
    "text": {"input": 2.50, "output": 10.00},          # gpt-4o
    "image": {
        # dall-e-3
        ("1024x1024", "standard"): 0.040,
        ("1792x1024", "standard"): 0.080,
        ("1024x1792", "standard"): 0.080,
        ("1024x1024", "hd"): 0.080,
        ("1792x1024", "hd"): 0.120,
        ("1024x1792", "hd"): 0.120,
        # gpt-image-1
        ("1024x1024", "low"): 0.011,
        ("1536x1024", "low"): 0.016,
        ("1024x1536", "low"): 0.016,
        ("1024x1024", "medium"): 0.042,
        ("1536x1024", "medium"): 0.063,
        ("1024x1536", "medium"): 0.063,
        ("1024x1024", "high"): 0.167,
        ("1536x1024", "high"): 0.250,
        ("1024x1536", "high"): 0.250,
    },
}


@dataclass
class UsageSnapshot:
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    images: int = 0
    image_cost: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        text = (self.input_tokens * _PRICES["text"]["input"]
                + self.output_tokens * _PRICES["text"]["output"]) / 1_000_000
        return text + self.image_cost

    def __sub__(self, other: "UsageSnapshot") -> "UsageSnapshot":
        return UsageSnapshot(
            input_tokens=self.input_tokens - other.input_tokens,
            output_tokens=self.output_tokens - other.output_tokens,
            requests=self.requests - other.requests,
            images=self.images - other.images,
            image_cost=self.image_cost - other.image_cost,
        )

    def report(self) -> str:
        parts = [
            f"{self.requests} API calls",
            f"{self.input_tokens:,} in + {self.output_tokens:,} out "
            f"= {self.total_tokens:,} tokens",
        ]
        if self.images:
            parts.append(f"{self.images} images")
        parts.append(f"~${self.estimated_cost:.3f}")
        return " | ".join(parts)


class UsageTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._totals = UsageSnapshot()

    def record_chat(self, usage) -> None:
        """Accepts both Chat Completions usage (prompt_tokens/...) and
        Responses API usage (input_tokens/...)."""
        if usage is None:
            return
        in_tok = getattr(usage, "prompt_tokens", None)
        out_tok = getattr(usage, "completion_tokens", None)
        if in_tok is None:
            in_tok = getattr(usage, "input_tokens", 0)
        if out_tok is None:
            out_tok = getattr(usage, "output_tokens", 0)
        with self._lock:
            self._totals.input_tokens += in_tok or 0
            self._totals.output_tokens += out_tok or 0
            self._totals.requests += 1

    def record_image(self, size: str, quality: str, usage=None) -> None:
        """Cost from the API's ACTUAL returned token usage when available
        (gpt-image-1 returns it: $5/1M text-in, $10/1M image-in, $40/1M
        image-out); otherwise the flat size+quality estimate (dall-e)."""
        cost = None
        if usage is not None:
            out_tok = getattr(usage, "output_tokens", 0) or 0
            in_tok = getattr(usage, "input_tokens", 0) or 0
            details = getattr(usage, "input_tokens_details", None)
            text_in = getattr(details, "text_tokens", None) if details else None
            img_in = getattr(details, "image_tokens", 0) if details else 0
            if out_tok:
                if text_in is None:
                    text_in, img_in = in_tok, 0
                cost = (text_in * 5 + img_in * 10 + out_tok * 40) / 1_000_000
        if cost is None:
            cost = _PRICES["image"].get((size, quality), 0.080)
        with self._lock:
            self._totals.images += 1
            self._totals.image_cost += cost
            self._totals.requests += 1

    def snapshot(self) -> UsageSnapshot:
        with self._lock:
            return UsageSnapshot(**vars(self._totals))

    def reset(self) -> None:
        with self._lock:
            self._totals = UsageSnapshot()


tracker = UsageTracker()
