"""CLI demo: change a deck's color theme without touching layout or text.

Usage:
    # See the deck's current colors (no API key needed)
    python examples/recolor_deck.py deck.pptx --show

    # Apply a preset palette (no API key needed)
    python examples/recolor_deck.py deck.pptx --preset terracotta -o out/recolored.pptx

    # Map specific colors yourself (no API key needed)
    python examples/recolor_deck.py deck.pptx --map "003C64=B85042,32E9CD=A7BEAE" -o out/recolored.pptx

    # Let GPT-4o pick a palette to match your topic (uses API key)
    python examples/recolor_deck.py deck.pptx --auto "a coffee subscription brand, warm and artisanal" -o out/recolored.pptx
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills.theme import (
    PRESETS, apply_palette, auto_map_palette, extract_palette, propose_palette,
)


def main():
    ap = argparse.ArgumentParser(description="Re-theme a .pptx (colors only, layout untouched)")
    ap.add_argument("deck", help="Path to the .pptx")
    ap.add_argument("--show", action="store_true", help="List current colors and exit")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="Apply a named palette")
    ap.add_argument("--map", dest="mapping", help='Manual mapping "OLD=NEW,OLD=NEW" (hex, no #)')
    ap.add_argument("--auto", metavar="BRIEF", help="GPT-4o picks a palette to fit this brief")
    ap.add_argument("-o", "--output", default="out/recolored.pptx")
    args = ap.parse_args()

    if not Path(args.deck).is_file():
        ap.error(f"file not found: {args.deck}\n"
                 "(check the path — and keep it in quotes if it contains spaces)")

    palette = extract_palette(args.deck)

    if args.show or not (args.preset or args.mapping or args.auto):
        print(f"{len(palette)} colors in {args.deck}:")
        for p in palette:
            kind = "dark" if p.luminance < 0.45 else "light" if p.luminance > 0.75 else "mid"
            print(f"  #{p.hex}  {p.count:4} uses  ({kind}, sat {p.saturation})")
        if not args.show:
            print("\nPick: --preset NAME | --map OLD=NEW,... | --auto \"brief\"")
            print(f"Presets: {', '.join(sorted(PRESETS))}")
        return

    if args.preset:
        mapping = auto_map_palette(palette, PRESETS[args.preset])
        print(f"Preset '{args.preset}':")
    elif args.mapping:
        mapping = dict(pair.split("=") for pair in args.mapping.split(","))
        print("Manual mapping:")
    else:
        print("Asking GPT-4o for a palette…")
        mapping = propose_palette(args.auto, palette)
        print("GPT-4o mapping:")

    for old, new in mapping.items():
        print(f"  #{old} -> #{new}")

    out = apply_palette(args.deck, mapping, args.output)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
