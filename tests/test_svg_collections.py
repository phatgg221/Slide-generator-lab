"""Offline tests for SVG collections — no API key needed.

Run:  python tests/test_svg_collections.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills.html_deck import build_html_deck
from slide_skills.svg_collections import (
    fill_svg, list_collections, retheme_svg, scan_collection, theme_mapping_for,
)
from slide_skills.theme import PRESETS, _luminance

ROOT = Path(__file__).resolve().parent.parent
STARTER = ROOT / "svg_templates" / "starter"
TMP = Path(__file__).resolve().parent / "tmp"
TMP.mkdir(exist_ok=True)


def main():
    # --- scan ---
    schema = scan_collection(STARTER)
    assert set(schema.slides) == {"title", "agenda", "section", "bullets",
                                  "statistic", "summary"}, schema.slide_types()
    title_ph = schema.slides["title"].placeholders
    assert title_ph["title"]["lines"] == 2, title_ph
    assert title_ph["title"]["max_chars"] == 24
    assert title_ph["subtitle"]["max_chars"] == 62
    assert schema.slides["statistic"].placeholders["stat_1"]["max_chars"] == 7
    assert schema.palette[:3] == ["1F2A44", "F6F1E7", "E4654F"], schema.palette
    print(f"✓ scan: 6 slide types, budgets parsed from |N syntax, palette loaded")

    # --- registry ---
    found = [c["name"] for c in list_collections(ROOT / "svg_templates")]
    assert "starter" in found, found
    print(f"✓ registry: {found}")

    # --- fill ---
    svg = (STARTER / "title.svg").read_text(encoding="utf-8")
    filled = fill_svg(svg, {
        "kicker": "KHÓA HỌC",
        "title": ["Machine", "Learning"],
        "subtitle": "Nhập môn cho sinh viên năm 2",
        "presenter": "Phát Huỳnh",
    })
    assert "Machine" in filled and "Learning" in filled
    assert "Nhập môn cho sinh viên năm 2" in filled
    assert "{{" not in filled, "unfilled placeholder leaked"
    print("✓ fill: strings + lists land, no {{}} leftovers")

    # --- retheme (contrast preserved) ---
    mapping = theme_mapping_for(STARTER, PRESETS["teal"])
    for old, new in mapping.items():
        assert abs(_luminance(old) - _luminance(new)) <= 0.2, (old, new)
    rethemed = retheme_svg(filled, mapping)
    assert "#1F2A44" not in rethemed and "#1f2a44" not in rethemed
    print(f"✓ retheme: {len(mapping)} colors remapped, contrast-safe")

    # --- html deck ---
    out = TMP / "starter_offline.html"
    build_html_deck([filled, rethemed], out, title="offline test", animation="rise")
    page = out.read_text(encoding="utf-8")
    assert page.count('<section class="slide"') == 2
    assert "@keyframes enter" in page and "animation-delay" in page
    assert "requestFullscreen" in page
    print(f"✓ html deck: 2 slides, animations + navigation embedded -> {out}")

    print("\nAll SVG collection checks passed.")


if __name__ == "__main__":
    main()
