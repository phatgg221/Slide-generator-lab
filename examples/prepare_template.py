"""CLI demo: ingest any .pptx into the template library.

Usage:
    # clean + GPT-4o classification -> library/my_template.pptx + .json
    python examples/prepare_template.py "~/Downloads/My Canva Design.pptx" my_template

    # also drop Canva's tutorial slides by index
    python examples/prepare_template.py design.pptx my_template --drop 13,14,15,16

    # list everything registered
    python examples/prepare_template.py --list
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills.template_maker import list_templates, prepare_template


def main():
    ap = argparse.ArgumentParser(description="Register a .pptx as a generation template")
    ap.add_argument("source", nargs="?", help="Path to the .pptx to ingest")
    ap.add_argument("name", nargs="?", help="Template name in the library")
    ap.add_argument("--drop", help="Slide indices to remove, e.g. 13,14,15,16")
    ap.add_argument("--no-classify", action="store_true",
                    help="Skip GPT-4o classification (generic slide_N types)")
    ap.add_argument("--list", action="store_true", help="List registered templates")
    args = ap.parse_args()

    if args.list:
        templates = list_templates()
        if not templates:
            print("No templates registered yet.")
        for t in templates:
            print(f"{t['name']}: {len(t['slide_types'])} usable slide types")
            for st in t["slide_types"]:
                desc = t["descriptions"].get(st, "")
                print(f"    {st:20} {desc[:70]}")
        return

    if not (args.source and args.name):
        ap.error("source and name are required (or use --list)")
    src = Path(args.source).expanduser()
    if not src.is_file():
        ap.error(f"file not found: {src}")

    drop = [int(i) for i in args.drop.split(",")] if args.drop else None
    result = prepare_template(src, args.name, drop_slides=drop,
                              classify=not args.no_classify)
    print(f"Registered template '{args.name}':")
    print(f"  deck:     {result['pptx']}")
    print(f"  manifest: {result['manifest']}")
    print("  slide types:")
    for t in result["types"]:
        print(f"    {t}")


if __name__ == "__main__":
    main()
