"""Skill 16: SVG template collections — folders of live-text SVG slides.

A *collection* is one visual style: a folder of SVG files, one per slide
type, designed in Figma/Inkscape with {{placeholders}} as the literal text:

    svg_templates/<collection>/
        collection.json     # optional: {description, palette, fonts, tags}
        title.svg           # slide type = filename stem
        statistic.svg ...

Placeholder syntax (visible and editable in the design tool):
    {{name}}        single-line text
    {{name|40}}     with an explicit character budget
    {{name.1}} {{name.2}}   multi-line: supply a list when filling

Main entry points:
    list_collections / scan_collection   -- registry + schema
    fill_svg / retheme_svg               -- pure-code transforms
    generate_deck_content                -- planner + GPT-4o fills the schema
    generate_web_deck                    -- brief -> animated deck.html
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from .config import get_client, TEXT_MODEL, load_guide
from .planner import MAX_SLIDES, MIN_SLIDES, SLIDE_TYPE_DESCRIPTIONS
from .theme import (
    PRESETS, PaletteColor, _contrast_safe, _luminance, _norm, _saturation,
    auto_map_palette,
)
from .usage import tracker

from .config import collections_dir as _collections_dir

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+(?:\.\d+)?)\s*(?:\|\s*(\d+))?\s*\}\}")
_HEX_RE = re.compile(r"#([0-9A-Fa-f]{6})\b")
_TEXT_BLOCK_RE = re.compile(r"<text\b[^>]*>.*?</text>", re.DOTALL)
_FONT_SIZE_RE = re.compile(r'font-size="?([\d.]+)')
_VIEWBOX_RE = re.compile(r'viewBox="[\d.\s-]*?([\d.]+)\s+([\d.]+)"\s*')


@dataclass
class SlideTemplate:
    slide_type: str
    file: str
    placeholders: dict = field(default_factory=dict)  # name -> {max_chars, lines, font_pt}


@dataclass
class CollectionSchema:
    name: str
    path: str
    description: str = ""
    palette: list[str] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)
    slides: dict[str, SlideTemplate] = field(default_factory=dict)

    def slide_types(self) -> list[str]:
        return list(self.slides)


def _estimate_budget(font_pt: float, viewbox_w: float) -> int:
    """Rough chars-that-fit when the designer gave no |N budget."""
    return max(8, int(viewbox_w * 0.6 / (font_pt * 0.55)))


def _scan_svg(svg: str) -> dict:
    """Placeholder metadata from one SVG's text content."""
    vb = _VIEWBOX_RE.search(svg)
    vb_w = float(vb.group(1)) if vb else 1440.0

    placeholders: dict[str, dict] = {}
    for block in _TEXT_BLOCK_RE.findall(svg):
        size_m = _FONT_SIZE_RE.search(block)
        font_pt = float(size_m.group(1)) if size_m else 16.0
        for m in _PLACEHOLDER_RE.finditer(block):
            raw, budget = m.group(1), m.group(2)
            base, line = raw, 0
            dot = re.match(r"(.+)\.(\d+)$", raw)
            if dot:
                base, line = dot.group(1), int(dot.group(2))
            entry = placeholders.setdefault(base, {
                "max_chars": 0, "lines": 1, "font_pt": font_pt})
            entry["lines"] = max(entry["lines"], line or 1)
            entry["font_pt"] = min(entry["font_pt"], font_pt)
            cap = int(budget) if budget else _estimate_budget(font_pt, vb_w)
            entry["max_chars"] = max(entry["max_chars"], cap)
    return placeholders


def scan_collection(collection_dir: Union[str, Path]) -> CollectionSchema:
    collection_dir = Path(collection_dir)
    if not collection_dir.is_dir():
        raise FileNotFoundError(f"collection not found: {collection_dir}")

    meta = {}
    meta_path = collection_dir / "collection.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    schema = CollectionSchema(
        name=collection_dir.name,
        path=str(collection_dir),
        description=str(meta.get("description", "")),
        palette=[_norm(c) for c in meta.get("palette", [])],
        fonts=[f.name for f in sorted(collection_dir.glob("*.[ot]tf"))],
    )
    for svg_file in sorted(collection_dir.glob("*.svg")):
        svg = svg_file.read_text(encoding="utf-8")
        schema.slides[svg_file.stem] = SlideTemplate(
            slide_type=svg_file.stem,
            file=svg_file.name,
            placeholders=_scan_svg(svg),
        )
    if not schema.slides:
        raise ValueError(f"no .svg files in {collection_dir}")

    if not schema.palette:
        schema.palette = [c.hex for c in extract_collection_palette(collection_dir)[:6]]
    return schema


def import_collection(
    src: Union[str, Path],
    name: str | None = None,
    *,
    base_dir: Union[str, Path, None] = None,
    overwrite: bool = False,
) -> dict:
    """Add a template collection to the library: copy a folder of .svg files
    (and optional collection.json) into the collections dir, then validate it.

    src   -- a folder of SVGs, OR a single .svg (becomes a 1-slide collection)
    name  -- collection name (defaults to the source folder/file stem)
    Returns the scanned schema summary; raises ValueError if no placeholders
    are found (likely outlined text instead of live <text>)."""
    src = Path(src)
    base = Path(base_dir) if base_dir is not None else _collections_dir()
    name = name or src.stem
    dest = base / name

    if dest.exists():
        if not overwrite:
            raise FileExistsError(
                f"Collection {name!r} already exists at {dest}. "
                "Pass overwrite=True to replace it.")
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        svgs = sorted(src.glob("*.svg"))
        if not svgs:
            raise ValueError(f"No .svg files in {src}")
        for f in svgs:
            shutil.copy2(f, dest / f.name)
        manifest = src / "collection.json"
        if manifest.exists():
            shutil.copy2(manifest, dest / "collection.json")
        for font in list(src.glob("*.ttf")) + list(src.glob("*.otf")):
            shutil.copy2(font, dest / font.name)
    elif src.suffix.lower() == ".svg":
        shutil.copy2(src, dest / src.name)
    else:
        raise ValueError(f"{src} is neither an .svg nor a folder of .svg files")

    schema = scan_collection(dest)   # raises if no live-text placeholders found
    total_ph = sum(len(s.placeholders) for s in schema.slides.values())
    return {
        "name": schema.name,
        "path": str(dest),
        "slide_types": list(schema.slides.keys()),
        "placeholders": total_ph,
    }


def list_collections(base_dir: Union[str, Path, None] = None) -> list[dict]:
    out = []
    base = Path(base_dir) if base_dir is not None else _collections_dir()
    if not base.is_dir():
        return out
    for child in sorted(base.iterdir()):
        if child.is_dir() and any(child.glob("*.svg")):
            try:
                schema = scan_collection(child)
            except ValueError:
                continue
            out.append({
                "name": schema.name,
                "description": schema.description,
                "slide_types": schema.slide_types(),
                "palette": schema.palette,
            })
    return out


def extract_collection_palette(collection_dir: Union[str, Path]) -> list[PaletteColor]:
    counts: dict[str, int] = {}
    for svg_file in Path(collection_dir).glob("*.svg"):
        for m in _HEX_RE.finditer(svg_file.read_text(encoding="utf-8")):
            c = _norm(m.group(1))
            counts[c] = counts.get(c, 0) + 1
    return sorted(
        (PaletteColor(c, n, round(_luminance(c), 3), round(_saturation(c), 3))
         for c, n in counts.items()),
        key=lambda p: -p.count,
    )


def fill_svg(svg: str, data: dict) -> str:
    """Substitute placeholders. Lists fill name.1/name.2/...; unknown
    placeholders become empty strings."""
    flat: dict[str, str] = {}
    for key, value in (data or {}).items():
        if isinstance(value, (list, tuple)):
            for i, item in enumerate(value, 1):
                flat[f"{key}.{i}"] = str(item)
            flat.setdefault(f"{key}.1", str(value[0]) if value else "")
        else:
            flat[key] = str(value)

    def sub(match):
        return flat.get(match.group(1), "")

    return _PLACEHOLDER_RE.sub(sub, svg)


def retheme_svg(svg: str, mapping: dict[str, str]) -> str:
    """Remap hex colors ({old: new}, no '#')."""
    mapping = {_norm(k): _norm(v) for k, v in mapping.items()}

    def sub(match):
        return "#" + mapping.get(_norm(match.group(1)), match.group(1))

    return _HEX_RE.sub(sub, svg)


def theme_mapping_for(
    collection_dir: Union[str, Path],
    target: Union[str, tuple, None],
) -> dict[str, str]:
    """Contrast-safe {old: new} mapping for a preset name, a (primary,
    secondary, accent) tuple, or None (no change)."""
    if target is None:
        return {}
    if isinstance(target, str):
        target = PRESETS[target]
    palette = extract_collection_palette(collection_dir)
    return auto_map_palette(palette, target)


# --------------------------------------------------------------------------
# AI: plan the deck and write the content

_FILL_SYSTEM = """\
You are a presentation writer filling SVG slide templates.

You get a brief and a list of available slide types, each with named text
placeholders and hard character budgets. Design the deck AND write the text.

Rules:
- Choose between {min_slides} and {max_slides} slides; types may repeat.
- Start with 'title' and end with 'summary' when those types exist.
- NEVER exceed a placeholder's max_chars — text gets cut off otherwise.
- Placeholders with lines > 1 take an ARRAY of up to that many short strings
  (one per line); you may supply fewer lines than the maximum.
- Fill EVERY placeholder of every slide you use.
- Keep one consistent narrative; write in the brief's language unless told.

Return ONLY JSON:
{{"deck_title": "...",
  "theme_preset": one of {presets} or null to keep the collection's colors,
  "slides": [{{"type": "<slide type>", "texts": {{"<placeholder>": "..." | ["...", "..."]}}}}]}}
"""


def generate_deck_content(
    schema: CollectionSchema,
    brief: str,
    *,
    language: str | None = None,
    temperature: float = 0.6,
) -> dict:
    """One GPT-4o call: plans the slide sequence and writes every
    placeholder. Returns {"deck_title", "theme_preset", "slides": [...]}."""
    client = get_client()

    catalog = {}
    for t, slide in schema.slides.items():
        catalog[t] = {
            "purpose": SLIDE_TYPE_DESCRIPTIONS.get(t, ""),
            "placeholders": {
                name: {"max_chars": p["max_chars"], "lines": p["lines"]}
                for name, p in slide.placeholders.items()
            },
        }

    user = (f"Brief:\n{brief}\n\nCollection: {schema.name} — {schema.description}\n"
            f"Available slide types:\n{json.dumps(catalog, ensure_ascii=False)}")
    if language:
        user += f"\n\nWrite all content in {language}."

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _FILL_SYSTEM.format(
                min_slides=MIN_SLIDES, max_slides=min(MAX_SLIDES, 15),
                presets=sorted(PRESETS)) + load_guide("style") + load_guide("color_theme")},
            {"role": "user", "content": user},
        ],
    )
    tracker.record_chat(response.usage)
    payload = json.loads(response.choices[0].message.content)

    slides = []
    for raw in payload.get("slides", []):
        slide_type = raw.get("type")
        if slide_type not in schema.slides:
            continue
        valid = schema.slides[slide_type].placeholders
        texts = {k: v for k, v in (raw.get("texts") or {}).items() if k in valid}
        slides.append({"type": slide_type, "texts": texts})
    if not slides:
        raise ValueError(f"model returned no usable slides: {payload}")

    preset = payload.get("theme_preset")
    return {
        "deck_title": str(payload.get("deck_title", "")),
        "theme_preset": preset if preset in PRESETS else None,
        "slides": slides,
    }


def generate_web_deck(
    collection: Union[str, Path],
    brief: str,
    output_path: Union[str, Path],
    *,
    palette: Union[str, tuple, None] = "auto",
    language: str | None = None,
    animation: str = "rise",
    base_dir: Union[str, Path, None] = None,
) -> dict:
    """brief -> animated self-contained deck.html. palette: preset name,
    (primary, secondary, accent) tuple, "auto" (AI decides), or None.

    The returned dict includes a "usage" summary (tokens + estimated cost)
    for this call."""
    from .html_deck import build_html_deck

    usage_before = tracker.snapshot()
    base = Path(base_dir) if base_dir is not None else _collections_dir()
    collection_dir = Path(collection)
    if not collection_dir.is_dir():
        collection_dir = base / str(collection)
    schema = scan_collection(collection_dir)

    content = generate_deck_content(schema, brief, language=language)

    target = palette
    if palette == "auto":
        target = content["theme_preset"]          # may be None -> keep colors
    mapping = theme_mapping_for(collection_dir, target)

    filled = []
    for entry in content["slides"]:
        svg = (collection_dir / schema.slides[entry["type"]].file).read_text(encoding="utf-8")
        svg = fill_svg(svg, entry["texts"])
        if mapping:
            svg = retheme_svg(svg, mapping)
        filled.append(svg)

    out = build_html_deck(filled, output_path,
                          title=content["deck_title"] or schema.name,
                          animation=animation)
    usage = tracker.snapshot() - usage_before
    return {
        "output_path": str(out),
        "deck_title": content["deck_title"],
        "slides": [e["type"] for e in content["slides"]],
        "theme": (target if isinstance(target, str) else
                  "custom" if target else "collection default"),
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
            "requests": usage.requests,
            "estimated_cost_usd": round(usage.estimated_cost, 4),
            "report": usage.report(),
        },
    }
