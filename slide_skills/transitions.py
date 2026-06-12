"""Skill 9: slide transitions.

Canva does not export its animations to .pptx (the download is fully
static), so this skill adds PowerPoint-native slide transitions to a
generated deck instead — the closest practical substitute.

    apply_transitions("deck.pptx", "deck.pptx", effect="fade")

Element-level entrance animations (per-shape) are deliberately out of
scope: their XML timing trees are fragile and PowerPoint-version-specific.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from pptx import Presentation
from pptx.oxml.ns import qn

# effect name -> (XML tag, attributes)
EFFECTS = {
    "fade":     ("p:fade", {}),
    "push":     ("p:push", {"dir": "u"}),
    "wipe":     ("p:wipe", {"dir": "l"}),
    "cover":    ("p:cover", {"dir": "l"}),
    "split":    ("p:split", {"orient": "horz", "dir": "out"}),
    "dissolve": ("p:dissolve", {}),
}

_SPEEDS = ("slow", "med", "fast")


def apply_transitions(
    pptx_path: Union[str, Path],
    output_path: Union[str, Path],
    *,
    effect: str = "fade",
    speed: str = "med",
    first_slide_effect: str | None = None,
) -> Path:
    """Set the same transition on every slide (replacing any existing one).
    first_slide_effect optionally gives slide 1 its own effect."""
    if effect not in EFFECTS:
        raise ValueError(f"Unknown effect {effect!r}. Available: {sorted(EFFECTS)}")
    if speed not in _SPEEDS:
        raise ValueError(f"speed must be one of {_SPEEDS}")

    prs = Presentation(str(pptx_path))
    for i, slide in enumerate(prs.slides):
        name = first_slide_effect if (i == 0 and first_slide_effect) else effect
        tag, attrs = EFFECTS[name]

        sld = slide._element
        for old in sld.findall(qn("p:transition")):
            sld.remove(old)

        transition = sld.makeelement(qn("p:transition"), {"spd": speed})
        transition.append(transition.makeelement(qn(tag), dict(attrs)))

        # schema order: cSld, clrMapOvr?, transition?, timing?
        anchor = sld.find(qn("p:clrMapOvr"))
        if anchor is None:
            anchor = sld.find(qn("p:cSld"))
        anchor.addnext(transition)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return output_path
