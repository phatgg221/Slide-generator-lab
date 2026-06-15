"""Skill 18: document → deck. Accept a rich-text outline (ProseMirror/TipTap
doc), infer a category per section, optionally research to add detail, pick a
theme, then map to template variants and assemble.

    generate_deck_from_document(doc, library_dir, "out/deck.html",
                                research=True, palette="auto", language="vi")

`doc` is the editor's JSON: {"type": "doc", "content": [heading, paragraph,
bulletList, blockquote, ...]} — a dict or a JSON string.

Pipeline (all agents reused):
  parse_document → [research] → map sections→categories+content (GPT-4o) →
  theme → generate_deck_from_plan (variant pick + fill + assemble)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .config import get_client, TEXT_MODEL, load_guide
from .svg_categories import generate_deck_from_plan, scan_template_library
from .usage import tracker


# --------------------------------------------------------------------------
# 1. Parse the ProseMirror/TipTap document into heading-delimited sections

def _node_text(node: dict) -> str:
    """Recursively extract plain text from a ProseMirror node."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    return "".join(_node_text(c) for c in node.get("content", []) or [])


def _list_items(node: dict) -> list[str]:
    """Text of each top-level list item."""
    items = []
    for li in node.get("content", []) or []:
        text = _node_text(li).strip()
        if text:
            items.append(text)
    return items


def parse_document(doc: Union[dict, str]) -> list[dict]:
    """Split a ProseMirror doc into sections, one per heading. Content before
    the first heading becomes a leading section. Each section:
        {"heading", "level", "text", "bullets": [...], "quotes": [...],
         "has_numbers": bool}
    """
    if isinstance(doc, str):
        doc = json.loads(doc)
    blocks = doc.get("content", []) if isinstance(doc, dict) else []

    sections: list[dict] = []
    current = {"heading": "", "level": 0, "paras": [], "bullets": [], "quotes": []}

    def flush():
        text = " ".join(current["paras"]).strip()
        body = "\n".join(filter(None, [
            text,
            "\n".join(f"- {b}" for b in current["bullets"]),
            "\n".join(f'"{q}"' for q in current["quotes"]),
        ]))
        if current["heading"] or body:
            joined = f"{current['heading']}\n{body}".strip()
            sections.append({
                "heading": current["heading"],
                "level": current["level"],
                "text": joined,
                "bullets": list(current["bullets"]),
                "quotes": list(current["quotes"]),
                "has_numbers": any(ch.isdigit() for ch in joined),
            })

    for block in blocks:
        btype = block.get("type")
        if btype == "heading":
            flush()
            current = {"heading": _node_text(block).strip(),
                       "level": block.get("attrs", {}).get("level", 1),
                       "paras": [], "bullets": [], "quotes": []}
        elif btype == "paragraph":
            t = _node_text(block).strip()
            if t:
                current["paras"].append(t)
        elif btype in ("bulletList", "orderedList"):
            current["bullets"].extend(_list_items(block))
        elif btype == "blockquote":
            q = _node_text(block).strip()
            if q:
                current["quotes"].append(q)
    flush()
    return sections


# --------------------------------------------------------------------------
# 2. Map sections → a category-named plan (GPT-4o infers categories)

_MAP_SYSTEM = """\
You turn a document outline into a slide plan. You are given the document's
sections and the AVAILABLE template categories (each with a purpose and
variant designs). For EACH slide you create:
- "category": choose the best-fitting category NAME from the available list
  (heading+bullets → a bullets/list category; a quote → a quote category;
  metrics/percentages → a KPI/stat category; the opening → a title category;
  the closing → a summary/CTA category).
- "topic": a short slide title.
- "talking_points": 2-5 tight, specific points drawn from (and elaborating on)
  that section's content — make them concrete, not generic.

Also choose an overall theme that fits the content's subject and mood.

Rules:
- Use ONLY category names from the available list. Don't invent categories.
- Keep the document's order and narrative. One idea per slide.
- Write in the document's language unless told otherwise.

Return ONLY JSON:
{"title": "...",
 "theme": {"preset": "<preset name>"} OR {"colors": {"primary":"RRGGBB",
   "secondary":"RRGGBB","accent":"RRGGBB"}},
 "slides": [{"category": "...", "topic": "...", "talking_points": ["...", ...]}]}
"""


def map_document_to_plan(
    sections: list[dict],
    library,
    *,
    research_summary: str = "",
    language: str | None = None,
    temperature: float = 0.5,
) -> dict:
    """GPT-4o assigns a category + detailed content to each section."""
    available = [
        {"category": c["category"], "purpose": c["purpose"],
         "variants": [v["name"] for v in c["variants"]]}
        for c in library.category_map()
    ]
    doc_view = [
        {"heading": s["heading"], "text": s["text"][:1200],
         "has_bullets": bool(s["bullets"]), "has_quote": bool(s["quotes"]),
         "has_numbers": s["has_numbers"]}
        for s in sections
    ]
    user = (
        f"Available categories:\n{json.dumps(available, ensure_ascii=False)}\n\n"
        f"Document sections (in order):\n{json.dumps(doc_view, ensure_ascii=False)}"
    )
    if research_summary:
        user += f"\n\nResearch findings (use to make points specific):\n{research_summary[:4000]}"
    if language:
        user += f"\n\nWrite all content in {language}."

    client = get_client()
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _MAP_SYSTEM
             + load_guide("style") + load_guide("color_theme")},
            {"role": "user", "content": user},
        ],
    )
    tracker.record_chat(response.usage)
    plan = json.loads(response.choices[0].message.content)

    # keep only slides whose category resolves to a real folder
    slides = []
    for s in plan.get("slides", []):
        if isinstance(s, dict) and library.resolve(str(s.get("category", ""))):
            slides.append(s)
    plan["slides"] = slides
    return plan


def _theme_to_palette(theme: dict):
    """Convert the planner's theme object into a palette arg."""
    if not isinstance(theme, dict):
        return None
    if "preset" in theme:
        from .theme import PRESETS
        return theme["preset"] if theme["preset"] in PRESETS else None
    if "colors" in theme:
        c = theme["colors"]
        try:
            return (c["primary"], c["secondary"], c["accent"])
        except (KeyError, TypeError):
            return None
    return None


# --------------------------------------------------------------------------
# 3. Orchestrate: document -> deck

def generate_deck_from_document(
    doc: Union[dict, str],
    library_dir: Union[str, Path],
    output_path: Union[str, Path],
    *,
    palette: Union[str, tuple, None] = "auto",
    language: str | None = None,
    animation: str = "rise",
    research: bool = False,
    title: str | None = None,
) -> dict:
    """Editor document -> animated web deck. palette="auto" lets the agent pick
    a theme from the content; a preset/tuple forces one; None keeps template
    colors. research=True enriches the content with web facts first."""
    usage_before = tracker.snapshot()

    sections = parse_document(doc)
    if not sections:
        raise ValueError("Document has no headings/content to turn into slides.")

    library = scan_template_library(library_dir)

    research_summary = ""
    if research:
        from .research import extract_keywords, web_research
        doc_text = "\n\n".join(s["text"] for s in sections)
        keywords = extract_keywords(doc_text)
        research_summary = web_research(doc_text, keywords).summary

    plan = map_document_to_plan(
        sections, library, research_summary=research_summary, language=language)
    if not plan["slides"]:
        raise ValueError(
            "No sections could be mapped to a category. Check that your "
            "template categories cover the document's content.")

    # palette: "auto" -> use the theme the agent chose; else honor the caller
    target = _theme_to_palette(plan.get("theme")) if palette == "auto" else palette

    result = generate_deck_from_plan(
        plan, library_dir, output_path,
        palette=target, language=language, animation=animation,
        title=title or plan.get("title"),
    )

    usage = tracker.snapshot() - usage_before
    result["usage"] = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "requests": usage.requests,
        "estimated_cost_usd": round(usage.estimated_cost, 4),
        "report": usage.report(),
    }
    result["plan"] = plan
    return result
