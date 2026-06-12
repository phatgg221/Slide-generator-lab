"""CLI for SVG collections -> animated web decks.

    python examples/web_deck.py list
    python examples/web_deck.py check starter
    python examples/web_deck.py demo starter -o out/starter_demo.html   # offline
    python examples/web_deck.py generate starter "Khóa học Machine Learning cơ bản" \
        -o out/deck.html [--palette teal] [--language Vietnamese] [--animation rise] [--pptx]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills.html_deck import ANIMATIONS, build_html_deck
from slide_skills.svg_collections import (
    DEFAULT_COLLECTIONS_DIR, fill_svg, generate_web_deck, list_collections,
    scan_collection,
)
from slide_skills.theme import PRESETS


def _resolve(name: str) -> Path:
    p = Path(name)
    return p if p.is_dir() else DEFAULT_COLLECTIONS_DIR / name


def cmd_list(args):
    collections = list_collections()
    if not collections:
        print(f"No collections in {DEFAULT_COLLECTIONS_DIR}/. See svg_templates/README.md")
    for c in collections:
        print(f"{c['name']}: {', '.join(c['slide_types'])}")
        if c["description"]:
            print(f"    {c['description']}")
        print(f"    palette: {' '.join('#' + p for p in c['palette'][:5])}")


def cmd_check(args):
    schema = scan_collection(_resolve(args.collection))
    print(f"Collection '{schema.name}': {len(schema.slides)} slide types")
    for t, slide in schema.slides.items():
        print(f"  {t}:")
        for name, p in slide.placeholders.items():
            shape = f"list[{p['lines']}]" if p["lines"] > 1 else "string"
            print(f"      {{{{{name}}}}}  {shape}, ≤{p['max_chars']} chars")


def _stub_value(name, meta):
    if meta["lines"] > 1:
        return [f"{name} line {i + 1}" for i in range(meta["lines"])]
    return name.replace("_", " ").title()[: meta["max_chars"]]


def cmd_demo(args):
    folder = _resolve(args.collection)
    schema = scan_collection(folder)
    svgs = []
    for t, slide in schema.slides.items():
        svg = (folder / slide.file).read_text(encoding="utf-8")
        data = {n: _stub_value(n, m) for n, m in slide.placeholders.items()}
        svgs.append(fill_svg(svg, data))
    out = args.output or f"out/{schema.name}_demo.html"
    build_html_deck(svgs, out, title=f"{schema.name} demo", animation=args.animation)
    print(f"Demo deck (every slide type, stub data): {out}")


def cmd_generate(args):
    palette = args.palette or "auto"
    result = generate_web_deck(
        args.collection, args.brief, args.output,
        palette=palette, language=args.language, animation=args.animation,
    )
    print(f"Deck: {result['output_path']}")
    print(f"  title:  {result['deck_title']}")
    print(f"  slides: {result['slides']}")
    print(f"  theme:  {result['theme']}")

    if args.pptx:
        print("PPTX export not wired for collections yet — open the HTML deck "
              "and print to PDF, or ask to enable render_svg_deck for collections.")


def main():
    ap = argparse.ArgumentParser(description="SVG collections -> animated web decks")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Show registered collections").set_defaults(func=cmd_list)

    p = sub.add_parser("check", help="Validate a collection, show placeholders")
    p.add_argument("collection")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("demo", help="Offline preview deck with stub data (free)")
    p.add_argument("collection")
    p.add_argument("-o", "--output", default=None)
    p.add_argument("--animation", choices=sorted(ANIMATIONS), default="rise")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("generate", help="GPT-4o plans + writes the deck")
    p.add_argument("collection")
    p.add_argument("brief")
    p.add_argument("-o", "--output", default="out/deck.html")
    p.add_argument("--palette", choices=sorted(PRESETS), default=None,
                   help="Force a theme (default: AI picks or keeps collection colors)")
    p.add_argument("--language", default=None)
    p.add_argument("--animation", choices=sorted(ANIMATIONS), default="rise")
    p.add_argument("--pptx", action="store_true")
    p.set_defaults(func=cmd_generate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
