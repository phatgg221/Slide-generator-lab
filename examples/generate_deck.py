"""CLI demo: fill a Canva template from a brief.

Usage:
    python examples/generate_deck.py template.pptx "A pitch deck about smart \
farming drones for Vietnamese rice farmers" -o out/deck.pptx
    python examples/generate_deck.py template.pptx "..." --no-images
    python examples/generate_deck.py template.pptx --inspect   # just show the spec
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills import SlideGeneratorAgent, parse_template


def main():
    ap = argparse.ArgumentParser(description="Fill a Canva .pptx template with AI content")
    ap.add_argument("template", help="Path to the Canva-exported .pptx")
    ap.add_argument("brief", nargs="?", help="What the presentation should be about")
    ap.add_argument("-f", "--brief-file", default=None,
                    help="Read the brief from a text/markdown file instead "
                         "(your outline, slide-by-slide notes, exact wording)")
    ap.add_argument("-o", "--output", default="out/deck.pptx")
    ap.add_argument("--language", default=None, help="e.g. 'Vietnamese'")
    ap.add_argument("--no-images", action="store_true", help="Skip DALL-E, keep template images")
    ap.add_argument("--hd", action="store_true", help="Use DALL-E HD quality")
    ap.add_argument("--inspect", action="store_true", help="Print the template spec and exit")
    args = ap.parse_args()

    if args.inspect:
        print(parse_template(args.template).to_json(indent=2))
        return

    brief = args.brief
    if args.brief_file:
        brief = Path(args.brief_file).read_text(encoding="utf-8")
    if not brief:
        ap.error("a brief (positional) or --brief-file is required unless --inspect is used")

    agent = SlideGeneratorAgent(
        generate_images=not args.no_images,
        image_quality="hd" if args.hd else "standard",
        on_progress=lambda msg: print(f"  • {msg}"),
    )
    result = agent.generate(args.template, brief, args.output, language=args.language)

    for w in result.warnings:
        print(f"  ⚠ {w}")
    print(f"\nSaved: {result.output_path} ({result.images_generated} images generated)")


if __name__ == "__main__":
    main()
