"""Skill 6: research agent — keywords from course content, then web search.

extract_keywords  -- GPT-4o pulls the key topics out of raw course content
web_research      -- searches the web for facts/stats/sources on those topics
                     (OpenAI web-search tool when the account has it, with a
                     model-knowledge fallback so the pipeline never blocks)
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .config import get_client, TEXT_MODEL
from .usage import tracker


@dataclass
class ResearchResult:
    summary: str
    method: str   # "web_search" | "web_search_preview" | "model-knowledge"


def extract_keywords(content: str, max_keywords: int = 10) -> list[str]:
    """The main topics/terms in the content, most important first."""
    client = get_client()
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Extract the most important keywords/topics from the user's "
                "content for research purposes. Return ONLY JSON: "
                f'{{"keywords": ["..."]}} with at most {max_keywords} items, '
                "most important first, in the content's language."
            )},
            {"role": "user", "content": content[:8000]},
        ],
    )
    tracker.record_chat(response.usage)
    payload = json.loads(response.choices[0].message.content)
    return [str(k) for k in payload.get("keywords", [])][:max_keywords]


def web_research(content: str, keywords: list[str]) -> ResearchResult:
    """Gather facts, statistics, definitions, and sources for the keywords.

    Tries OpenAI's web-search tool (Responses API); if the account/model
    doesn't support it, falls back to GPT-4o's own knowledge and says so."""
    client = get_client()
    prompt = (
        "Research the following topics to prepare a presentation.\n"
        f"Topics: {', '.join(keywords)}\n\n"
        f"Context (the course content):\n{content[:3000]}\n\n"
        "Return a structured research brief: key facts, definitions, recent "
        "statistics WITH their numbers, notable examples, and a short list of "
        "sources. Write it in the same language as the context."
    )

    for tool_type in ("web_search", "web_search_preview"):
        try:
            response = client.responses.create(
                model=TEXT_MODEL,
                tools=[{"type": tool_type}],
                input=prompt,
            )
            tracker.record_chat(getattr(response, "usage", None))
            return ResearchResult(summary=response.output_text, method=tool_type)
        except Exception:
            continue

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": (
                "You are a research assistant. Web search is unavailable, so "
                "answer from your own knowledge and avoid invented statistics "
                "— give ranges or say 'approximately' where unsure."
            )},
            {"role": "user", "content": prompt},
        ],
    )
    tracker.record_chat(response.usage)
    return ResearchResult(
        summary=response.choices[0].message.content,
        method="model-knowledge",
    )
