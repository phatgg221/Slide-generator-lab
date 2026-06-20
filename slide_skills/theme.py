"""Skill 5: color-theme extraction and replacement.

Canva exports hardcode every color as <a:srgbClr val="RRGGBB"/> in the slide
XML (no PowerPoint theme references), so re-theming is a palette remap:

    extract_palette  -- census of every hardcoded color and how often it's used
    auto_map_palette -- map template colors onto a preset (or any 3-color
                        palette) by luminance, keeping black/white untouched
    propose_palette  -- GPT-4o picks a content-appropriate mapping (agent-ready)
    apply_palette    -- rewrite the colors into a new .pptx; layout untouched

Only shape fills, lines, text colors, and gradient stops change. Colors baked
into raster images (decorative PNG/JPEG) stay as they are; embedded SVGs are
recolored too since they're text.
"""

from __future__ import annotations

import colorsys
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from .config import get_client, TEXT_MODEL, load_guide
from .usage import tracker

# Palettes as (primary=dark, secondary=light, accent=vivid). Role order
# matters: auto_map_palette sends dark template colors to primary, pale ones
# to secondary, saturated ones to accent — and then corrects lightness, so
# text/background contrast survives any palette.
PRESETS = {
    "midnight":   ("1E2761", "CADCFC", "4F6BD8"),
    "forest":     ("2C5F2D", "EAF2E0", "97BC62"),
    "coral":      ("2F3C7E", "F9E795", "F96167"),
    "terracotta": ("B85042", "E7E8D1", "A7BEAE"),
    "ocean":      ("065A82", "D6EAF5", "1C7293"),
    "teal":       ("028090", "E0F5F2", "02C39A"),
    "berry":      ("6D2E46", "ECE2D0", "A26769"),
    "cherry":     ("990011", "FCF6F5", "2F3C7E"),
}

_COLORABLE_PARTS = re.compile(r"ppt/(slides|slideLayouts|slideMasters)/[^/]+\.xml$")
_SRGB = re.compile(r'srgbClr val="([0-9A-Fa-f]{6})"')


@dataclass
class PaletteColor:
    hex: str
    count: int
    luminance: float    # 0 black .. 1 white
    saturation: float   # 0 grey .. 1 vivid


def _norm(hex_color: str) -> str:
    return hex_color.upper().lstrip("#")


def _luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _saturation(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[1]


def _match_lightness(target_hex: str, reference_hex: str) -> str:
    """Take target's hue/saturation, at the perceived luminance the
    template's designer chose for that spot. Luminance grows monotonically
    with HLS lightness, so binary-search the lightness."""
    tr, tg, tb = (int(target_hex[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, _, s = colorsys.rgb_to_hls(tr, tg, tb)
    ref_lum = _luminance(reference_hex)
    lo, hi = 0.0, 1.0
    r = g = b = 0.0
    for _ in range(20):
        mid = (lo + hi) / 2
        r, g, b = colorsys.hls_to_rgb(h, mid, s)
        if 0.2126 * r + 0.7152 * g + 0.0722 * b < ref_lum:
            lo = mid
        else:
            hi = mid
    return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _contrast_safe(new_hex: str, old_hex: str, max_drift: float = 0.18) -> str:
    """If a replacement changes a color's luminance enough to break dark-on-
    light relationships (titles vanishing into backgrounds), re-anchor the
    replacement at the original lightness."""
    if abs(_luminance(new_hex) - _luminance(old_hex)) > max_drift:
        return _match_lightness(new_hex, old_hex)
    return new_hex


def extract_palette(pptx_path: Union[str, Path]) -> list[PaletteColor]:
    """Every hardcoded color in the deck, most used first."""
    counts: dict[str, int] = {}
    with zipfile.ZipFile(str(pptx_path)) as z:
        for name in z.namelist():
            if _COLORABLE_PARTS.match(name):
                for match in _SRGB.findall(z.read(name).decode("utf-8", "ignore")):
                    counts[_norm(match)] = counts.get(_norm(match), 0) + 1
    return sorted(
        (PaletteColor(c, n, round(_luminance(c), 3), round(_saturation(c), 3))
         for c, n in counts.items()),
        key=lambda p: -p.count,
    )


def auto_map_palette(
    palette: list[PaletteColor],
    target: tuple[str, str, str],
) -> dict[str, str]:
    """Map template colors onto (primary, secondary, accent): vivid mid/light
    colors play the accent role, dark colors -> primary, pale -> secondary.
    Pure black and white are left alone (they're usually text and must stay
    readable)."""
    primary, secondary, accent = (_norm(c) for c in target)
    mapping: dict[str, str] = {}
    for color in palette:
        if color.hex in ("000000", "FFFFFF"):
            continue
        # Vivid colors are accents BY INTENT (e.g. neon highlights on a dark
        # deck) — map them to the target accent VERBATIM, keeping them vivid.
        # Luminance-clamping them would darken a low-luminance accent like
        # hot-pink into the background and make it vanish.
        if color.saturation >= 0.55:
            mapping[color.hex] = accent
            continue
        if color.luminance < 0.45:
            new = primary
        elif color.luminance > 0.75:
            new = secondary
        else:
            new = accent
        mapping[color.hex] = _contrast_safe(new, color.hex)
    return {old: new for old, new in mapping.items() if old != new}


def propose_palette(
    brief: str,
    palette: list[PaletteColor],
    *,
    temperature: float = 0.7,
) -> dict[str, str]:
    """GPT-4o picks a content-appropriate palette and returns {old: new} hex
    mapping. This is the piece a theming agent calls."""
    client = get_client()
    current = [
        {"hex": p.hex, "uses": p.count, "luminance": p.luminance, "saturation": p.saturation}
        for p in palette
    ]
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "You are a presentation art director. Given a brief and the "
                "current color palette of a slide template, choose a new "
                "palette that fits the brief's topic and mood.\n"
                "Rules:\n"
                "- Map every current color to a new hex color.\n"
                "- Preserve each color's approximate luminance so text stays "
                "readable on its background (dark stays dark, light stays light).\n"
                "- Keep pure #000000 and #FFFFFF unchanged.\n"
                "- One dominant hue family plus one accent; don't use more "
                "distinct hues than the original.\n"
                'Return ONLY JSON: {"mapping": {"RRGGBB": "RRGGBB", ...}, '
                '"rationale": "one sentence"}'
                + load_guide("color_theme")
            )},
            {"role": "user", "content": (
                f"Brief:\n{brief}\n\nCurrent palette:\n{json.dumps(current)}"
            )},
        ],
    )
    tracker.record_chat(response.usage)
    payload = json.loads(response.choices[0].message.content)
    valid = {p.hex for p in palette}
    mapping = {}
    for old, new in (payload.get("mapping") or {}).items():
        old, new = _norm(old), _norm(new)
        if (old in valid and re.fullmatch(r"[0-9A-F]{6}", new)
                and old != new and old not in ("000000", "FFFFFF")):
            mapping[old] = _contrast_safe(new, old)
    return {o: n for o, n in mapping.items() if o != n}


def apply_palette(
    pptx_path: Union[str, Path],
    mapping: dict[str, str],
    output_path: Union[str, Path],
    *,
    recolor_svg: bool = True,
) -> Path:
    """Write a copy of the deck with colors remapped ({old_hex: new_hex}).
    Only color values change — layout, text, and images are untouched."""
    mapping = {_norm(k): _norm(v) for k, v in mapping.items()}
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(str(pptx_path)) as zin, \
         zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if _COLORABLE_PARTS.match(item.filename):
                text = data.decode("utf-8")
                for old, new in mapping.items():
                    text = re.sub(
                        f'(srgbClr val=")({old})(")', rf"\g<1>{new}\g<3>",
                        text, flags=re.IGNORECASE,
                    )
                data = text.encode("utf-8")
            elif recolor_svg and item.filename.endswith(".svg"):
                text = data.decode("utf-8", "ignore")
                for old, new in mapping.items():
                    text = re.sub(f"#{old}", f"#{new}", text, flags=re.IGNORECASE)
                data = text.encode("utf-8")
            zout.writestr(item, data)
    return output_path
