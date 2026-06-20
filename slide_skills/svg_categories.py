"""Skill 17: category template library + variant-selecting agent.

A *template library* is a folder of CATEGORIES, each holding several SVG
*variants* — different designs that serve the same layout function:

    templates/
        TITLE_SLIDE/      variant_a.svg  variant_b.svg ...
        KPI_BIG_NUMBER/   variant_a.svg  variant_b.svg ...
        CHART_INSIGHT/    ...

The user supplies a PLAN: an ordered list of slides, each naming a category
(matching a folder) plus the content/research for that slide. For each
planned slide the agent:

  1. schema-fit pre-filter — keep variants whose placeholder slots can hold
     the slide's content (right number of bullets/stats, etc.)
  2. one GPT-4o call — pick the best-fitting variant among the finalists AND
     write its placeholder values from the content

Then fill + retheme + assemble into an animated web deck (reusing the SVG
collection machinery).

Folder/category names are matched case-insensitively, ignoring spaces, '&',
'/', '-' and '_', so plan labels like "KPI & Big Numbers" map to KPI_BIG_NUMBER.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from .config import get_client, TEXT_MODEL, load_guide
from .svg_collections import (
    _scan_svg, embed_image, fill_svg, retheme_svg, scan_image_placeholders,
)
from .theme import (
    PRESETS, PaletteColor, _luminance, _norm, _saturation, auto_map_palette,
)
from .usage import tracker

_HEX_RE = re.compile(r"#([0-9A-Fa-f]{6})\b")


def _library_palette(lib: "TemplateLibrary") -> list[PaletteColor]:
    """All hex colors across every variant in the library, most-used first."""
    counts: dict[str, int] = {}
    for variants in lib.categories.values():
        for v in variants:
            for m in _HEX_RE.finditer(Path(v.path).read_text(encoding="utf-8")):
                c = _norm(m.group(1))
                counts[c] = counts.get(c, 0) + 1
    return sorted(
        (PaletteColor(c, n, round(_luminance(c), 3), round(_saturation(c), 3))
         for c, n in counts.items()),
        key=lambda p: -p.count,
    )


@dataclass
class Variant:
    category: str
    name: str                       # filename stem
    file: str
    path: str
    description: str = ""            # "when to use this design" (from category.json)
    placeholders: dict = field(default_factory=dict)   # name -> {max_chars, lines, font_pt}
    image_placeholders: list = field(default_factory=list)   # <image> slot names
    field_specs: dict = field(default_factory=dict)    # name -> {type, desc} from schema.json

    def slot_summary(self) -> dict:
        """Compact spec for the selection prompt: what it's for + each slot's
        budget, plus type/desc when a <variant> schema.json provides them
        (so the model knows what each field MEANS, not just its length)."""
        slots = {}
        for name, m in self.placeholders.items():
            entry = {"max_chars": m["max_chars"], "lines": m["lines"]}
            spec = self.field_specs.get(name)
            if spec:
                if spec.get("type"):
                    entry["type"] = spec["type"]
                if spec.get("desc"):
                    entry["desc"] = spec["desc"]
            slots[name] = entry
        return {"description": self.description, "slots": slots}


@dataclass
class TemplateLibrary:
    base_dir: str
    categories: dict[str, list[Variant]] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)   # category -> purpose

    def category_names(self) -> list[str]:
        return list(self.categories)

    def resolve(self, label: str) -> str | None:
        """Map a plan label ('KPI & Big Numbers') to a category key."""
        want = _canon(label)
        for key in self.categories:
            if _canon(key) == want:
                return key
        return None

    def category_map(self) -> list[dict]:
        """Registry of every category + its variants — feed this to the
        planner so it only picks categories that exist, and to a UI so users
        see what's available."""
        return [
            {
                "category": cat,
                "purpose": self.descriptions.get(cat, ""),
                "variants": [{"name": v.name, "description": v.description}
                             for v in variants],
            }
            for cat, variants in self.categories.items()
        ]


def _canon(s: str) -> str:
    return re.sub(r"[\s&/_-]+", "", s).lower()


def _load_field_specs(svg_file: Path) -> dict:
    """Optional per-variant schema: <stem>.schema.json or <stem>_schema.json
    next to the SVG. Returns {field_name: {type, desc}} or {} if absent.
    Budgets (max_chars/lines) always come from the SVG, so they stay in sync."""
    for cand in (svg_file.with_suffix(".schema.json"),
                 svg_file.with_name(svg_file.stem + "_schema.json")):
        if cand.exists():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return {}
            return {str(k): v for k, v in (data.get("fields") or {}).items()}
    return {}


def scan_template_library(base_dir: Union[str, Path]) -> TemplateLibrary:
    """Discover categories (subfolders) and their variant SVGs."""
    base = Path(base_dir)
    if not base.is_dir():
        raise FileNotFoundError(f"template library not found: {base}")

    lib = TemplateLibrary(base_dir=str(base))
    for cat_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        # optional category.json: {"description": "...",
        #                          "variants": {"<name>": "when to use it"}}
        meta = {}
        meta_path = cat_dir / "category.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        var_desc = meta.get("variants", {}) or {}

        variants = []
        for svg_file in sorted(cat_dir.glob("*.svg")):
            svg_text = svg_file.read_text(encoding="utf-8")
            variants.append(Variant(
                category=cat_dir.name,
                name=svg_file.stem,
                file=svg_file.name,
                path=str(svg_file),
                description=str(var_desc.get(svg_file.stem, "")),
                placeholders=_scan_svg(svg_text),
                image_placeholders=scan_image_placeholders(svg_text),
                field_specs=_load_field_specs(svg_file),
            ))
        if variants:
            lib.categories[cat_dir.name] = variants
            lib.descriptions[cat_dir.name] = str(meta.get("description", ""))
    if not lib.categories:
        raise ValueError(
            f"No category folders with .svg files under {base}. Expected "
            "templates/<CATEGORY>/<variant>.svg")
    return lib


def _content_size(slide_content: dict) -> int:
    """How many discrete items the slide's content implies (bullets, stats…)."""
    points = slide_content.get("talking_points") or slide_content.get("points") or []
    if isinstance(points, (list, tuple)):
        return len(points)
    return 1


def _capacity(variant: Variant) -> int:
    """How many repeatable content slots a variant exposes — counts
    numbered placeholder families (body, item_1/2/3…) and lines."""
    families: dict[str, int] = {}
    for name, meta in variant.placeholders.items():
        fam = re.sub(r"_?\d+$", "", name)
        families[fam] = families.get(fam, 0) + max(meta.get("lines", 1), 1)
    # the largest repeatable family approximates the slide's item capacity
    return max(families.values()) if families else 0


def shortlist_variants(variants: list[Variant], slide_content: dict,
                       k: int = 4) -> list[Variant]:
    """Schema-fit pre-filter: rank variants by how well their capacity matches
    the content's item count; return the top k. Pure code, no AI."""
    need = _content_size(slide_content)

    def score(v: Variant) -> tuple:
        cap = _capacity(v)
        fits = cap >= need                      # can hold all items?
        waste = abs(cap - need)                 # closeness
        return (0 if fits else 1, waste, v.name)

    return sorted(variants, key=score)[:k]


_SELECT_SYSTEM = """\
You place one slide of a presentation. You are given the slide's content and
several candidate template variants. Each variant has a "description" (when
that design is the right choice) and "slots" (named placeholders with hard
character budgets). Do TWO things:

1. Choose the variant whose description AND slots best fit this content —
   match the design intent, and don't pick a variant with far too few or too
   many slots for the data.
2. Write the text for EVERY placeholder ("slots") of the chosen variant.

Rules:
- NEVER exceed a placeholder's max_chars (text is clipped otherwise).
- A placeholder with lines > 1 takes an ARRAY of up to that many short
  strings; you may supply fewer.
- Fill EVERY placeholder with meaningful content — never leave one empty or
  blank (an empty slot renders as a broken empty box).
- A placeholder named like a number/stat (stat, value, number, metric, kpi,
  percent) MUST contain an actual figure (e.g. "78%", "3×", "12M"). If the
  content lacks one, derive a reasonable, clearly-rounded number from the
  topic (prefix "~" if approximate). Never put a non-number there or leave it blank.
- Write in the content's language.

Return ONLY JSON:
{"variant": "<variant name>", "texts": {"<placeholder>": "..." | ["...", "..."]}}
"""


def select_and_fill_slide(variants: list[Variant], slide_content: dict,
                          *, language: str | None = None,
                          shortlist_k: int = 4) -> dict:
    """Schema-fit shortlist + one GPT-4o call -> {"variant", "texts"} for the
    chosen variant. Returns {} if no variant can be selected."""
    if not variants:
        return {}
    finalists = shortlist_variants(variants, slide_content, k=shortlist_k)
    candidates = {v.name: v.slot_summary() for v in finalists}

    user = (
        f"Slide content:\n{json.dumps(slide_content, ensure_ascii=False)}\n\n"
        f"Candidate variants and their placeholders:\n"
        f"{json.dumps(candidates, ensure_ascii=False)}"
    )
    if language:
        user += f"\n\nWrite all text in {language}."

    client = get_client()
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=0.6,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": _SELECT_SYSTEM + load_guide("style")},
                  {"role": "user", "content": user}],
    )
    tracker.record_chat(response.usage)
    payload = json.loads(response.choices[0].message.content)

    chosen = payload.get("variant")
    by_name = {v.name: v for v in finalists}
    if chosen not in by_name:                       # model picked outside shortlist
        chosen = finalists[0].name
    variant = by_name[chosen]
    texts = {k: v for k, v in (payload.get("texts") or {}).items()
             if k in variant.placeholders}
    return {"variant": variant, "texts": texts}


def _image_prompt(slide: dict, name: str) -> str:
    """Build an image prompt that REPRESENTS the slide's content (concrete
    subject), not generic decoration."""
    topic = slide.get("topic") or slide.get("heading") or ""
    points = slide.get("talking_points") or slide.get("points") or []
    pts = "; ".join(str(p) for p in points) if isinstance(points, (list, tuple)) else ""
    return (
        f"A clear, representational flat-style illustration that visually "
        f"explains this slide's concept: \"{topic}\". "
        f"Depict concrete subjects, objects, or a scene a viewer would "
        f"associate with: {pts}. Modern editorial vector look, cohesive color "
        f"palette, simple background. No text, no words, no letters, no labels."
    ).strip()


def _fill_images(svg, variant, slide, image_source, warnings, idx):
    """Generate + embed a picture for each image placeholder in the variant."""
    if image_source == "ai":
        from .image_generator import generate_image as _gen
    else:
        from .svg_image_generator import generate_svg_image as _gen
    for name in variant.image_placeholders:
        try:
            png = _gen(_image_prompt(slide, name), aspect_ratio=1.4)
            svg = embed_image(svg, name, png)
        except Exception as exc:
            warnings.append(f"Slide {idx}: image {name!r} failed ({exc}); slot left empty.")
    return svg


def generate_deck_from_plan(
    plan: Union[list, dict],
    library_dir: Union[str, Path],
    output_path: Union[str, Path],
    *,
    palette: Union[str, tuple, None] = None,
    language: str | None = None,
    animation: str = "rise",
    images: bool = False,
    image_source: str = "svg",      # "svg" (cheap vector) | "ai" (photo model)
    title: str | None = None,
) -> dict:
    """Build an animated web deck from a category-named plan.

    plan: list of slides, each {"category": "<folder/label>", ...content...}
          (or {"slides": [...], "title": ...}). Content keys like
          "topic"/"talking_points"/"data" guide the agent.
    images=True fills any <image> placeholders in the chosen variants with a
    generated picture (image_source "svg" = GPT-4o vector ~$0.005, "ai" =
    gpt-image-1 photo).
    """
    from .html_deck import build_html_deck

    usage_before = tracker.snapshot()
    if isinstance(plan, dict):
        title = title or plan.get("title") or plan.get("deck_title")
        slides = plan.get("slides", [])
    else:
        slides = plan

    lib = scan_template_library(library_dir)

    # color mapping computed once from the whole library's palette.
    # Unknown preset names (incl. "auto") are ignored -> keep template colors.
    mapping = {}
    target = PRESETS.get(palette) if isinstance(palette, str) else palette
    if target is not None:
        mapping = auto_map_palette(_library_palette(lib), target)

    filled_svgs, chosen, warnings = [], [], []
    for i, slide in enumerate(slides):
        label = slide.get("category") or slide.get("type") or ""
        key = lib.resolve(label)
        if key is None:
            warnings.append(f"Slide {i}: no category matches {label!r}; skipped.")
            continue
        result = select_and_fill_slide(
            lib.categories[key], slide, language=language)
        if not result:
            warnings.append(f"Slide {i} ({label}): no variant selected; skipped.")
            continue
        variant = result["variant"]
        svg = Path(variant.path).read_text(encoding="utf-8")
        svg = fill_svg(svg, result["texts"])
        if images and variant.image_placeholders:
            svg = _fill_images(svg, variant, slide, image_source, warnings, i)
        if mapping:
            svg = retheme_svg(svg, mapping)
        filled_svgs.append(svg)
        chosen.append({"category": key, "variant": variant.name})

    if not filled_svgs:
        raise ValueError(f"No slides could be built. Warnings: {warnings}")

    out = build_html_deck(filled_svgs, output_path,
                          title=title or "Presentation", animation=animation)
    usage = tracker.snapshot() - usage_before
    return {
        "output_path": str(out),
        "slides": chosen,
        "warnings": warnings,
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "requests": usage.requests,
            "estimated_cost_usd": round(usage.estimated_cost, 4),
            "report": usage.report(),
        },
    }
