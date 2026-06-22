"""Skill 6: research agent — keywords from course content, then web search.

extract_keywords  -- GPT-4o pulls the key topics out of raw course content
web_research      -- searches the web for facts/stats/sources on those topics

Search backend priority (first available wins):
  1. Tavily        -- if TAVILY_API_KEY is set (LLM-grade search, any account)
  2. model-knowledge -- the model's own knowledge, so the pipeline never blocks

The OpenAI hosted web_search tool is OFF by default (it can pull large page
content into the prompt and inflate tokens). Re-enable with the env var
SLIDE_ENABLE_OPENAI_WEBSEARCH=1.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .config import get_client, TEXT_MODEL, resolve_tavily_key
from .usage import tracker


@dataclass
class ResearchResult:
    summary: str
    method: str   # "tavily" | "web_search" | "web_search_preview" | "model-knowledge"
    sources: list = None   # [{title, url}] when the backend provides them


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


def _tavily_research(content: str, keywords: list[str], prompt: str) -> ResearchResult | None:
    """Search with Tavily, then have GPT-4o synthesize the results into a
    structured brief. Returns None if Tavily isn't available."""
    api_key = resolve_tavily_key()
    if not api_key:
        return None
    try:
        from tavily import TavilyClient
    except ImportError:
        return None

    try:
        tv = TavilyClient(api_key=api_key)
        query = ", ".join(keywords) if keywords else content[:380]
        res = tv.search(query=query, max_results=6, include_answer=True,
                        search_depth="advanced")
    except Exception:
        return None

    results = res.get("results", [])
    sources = [{"title": r.get("title", ""), "url": r.get("url", "")} for r in results]
    context = ""
    if res.get("answer"):
        context += f"Search answer: {res['answer']}\n\n"
    for r in results:
        context += f"- {r.get('title','')} ({r.get('url','')}): {r.get('content','')}\n"

    # synthesize grounded brief with GPT-4o (token usage tracked here)
    client = get_client()
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": (
                "You are a research assistant. Using ONLY the supplied web "
                "search results, write a structured research brief: key facts, "
                "definitions, recent statistics WITH numbers, notable examples. "
                "Cite sources inline by title. Write in the context's language.")},
            {"role": "user", "content": f"{prompt}\n\nWeb search results:\n{context}"},
        ],
    )
    tracker.record_chat(response.usage)
    return ResearchResult(
        summary=response.choices[0].message.content,
        method="tavily",
        sources=sources,
    )


def web_research(content: str, keywords: list[str]) -> ResearchResult:
    """Gather facts, statistics, definitions, and sources for the keywords.

    Backend priority: Tavily (TAVILY_API_KEY) -> GPT model knowledge.
    The OpenAI hosted web-search tool is DISABLED by default (set
    SLIDE_ENABLE_OPENAI_WEBSEARCH=1 to re-enable). Always returns a
    ResearchResult; the .method field says which backend was used."""
    client = get_client()
    prompt = (
        "Research the following topics to prepare a presentation.\n"
        f"Topics: {', '.join(keywords)}\n\n"
        f"Context (the course content):\n{content[:3000]}\n\n"
        "Return a structured research brief: key facts, definitions, recent "
        "statistics WITH their numbers, notable examples, and a short list of "
        "sources. Write it in the same language as the context."
    )

    tavily = _tavily_research(content, keywords, prompt)
    if tavily is not None:
        return tavily

    # OpenAI hosted web_search tool is opt-in only (it can pull large amounts
    # of page content into the prompt, inflating tokens). Off unless asked.
    if os.getenv("SLIDE_ENABLE_OPENAI_WEBSEARCH") == "1":
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
