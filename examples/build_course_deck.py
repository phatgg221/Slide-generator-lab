"""CLI demo: course content -> researched, planned, themed deck.

Usage:
    python examples/build_course_deck.py library/slide_library.pptx \
        -f my_course_notes.md -o out/course_deck.pptx

    # quick/cheap test: no web research, no DALL-E
    python examples/build_course_deck.py library/slide_library.pptx \
        "Machine learning basics: supervised vs unsupervised..." \
        --no-research --no-images

    # check the library file is set up correctly (no API key needed)
    python examples/build_course_deck.py library/slide_library.pptx --check
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills.assembler import load_library_types
from slide_skills.pipeline import CourseDeckPipeline
from slide_skills.template_parser import parse_template
from slide_skills.theme import PRESETS
from slide_skills.animations import ENTRANCE_EFFECTS, add_animations
from slide_skills.transitions import EFFECTS, apply_transitions


def check_library(path: str) -> None:
    types = load_library_types(path)
    spec = parse_template(path)
    print(f"Library OK: {len(types)} slides")
    for t, s in zip(types, spec.slides):
        print(f"  {s.index}: {t:11} {len(s.texts)} text boxes, {len(s.images)} images")
    no_text = [t for t, s in zip(types, spec.slides) if not s.texts]
    if no_text:
        print(f"  ⚠ no fillable text found on: {', '.join(no_text)}")


def main():
    ap = argparse.ArgumentParser(description="Build a course deck from a slide library")
    ap.add_argument("library", help="Path to the slide library .pptx")
    ap.add_argument("content", nargs="?", help="Course content (or use -f)")
    ap.add_argument("-f", "--content-file", help="Read course content from a file")
    ap.add_argument("-o", "--output", default="out/course_deck.pptx")
    ap.add_argument("--language", default=None)
    ap.add_argument("--theme", choices=sorted(PRESETS), help="Force a theme preset")
    ap.add_argument("--transition", choices=sorted(EFFECTS),
                    help="Add a slide transition to every slide (e.g. fade)")
    ap.add_argument("--animate", choices=sorted(ENTRANCE_EFFECTS),
                    help="Add entrance animations to shapes (e.g. fade)")
    ap.add_argument("--animate-on-click", action="store_true",
                    help="Animations advance per click instead of automatically")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--svg-images", action="store_true",
                    help="GPT-4o draws flat vector illustrations instead of an "
                         "image model (~5x cheaper, illustration style)")
    ap.add_argument("--no-research", action="store_true")
    ap.add_argument("--check", action="store_true", help="Validate the library and exit")
    args = ap.parse_args()

    if not Path(args.library).is_file():
        ap.error(f"library not found: {args.library}")
    if args.check:
        check_library(args.library)
        return

    content = args.content
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")
    if not content:
        ap.error("course content (positional) or --content-file is required")

    pipeline = CourseDeckPipeline(
        generate_images=not args.no_images,
        image_source="svg" if args.svg_images else "ai",
        do_research=not args.no_research,
        on_progress=lambda msg: print(f"  • {msg}"),
    )
    result = pipeline.build(
        content, args.library, args.output,
        language=args.language, theme_override=args.theme,
    )

    if args.transition:
        apply_transitions(result.output_path, result.output_path, effect=args.transition)
        print(f"  • Added '{args.transition}' transitions to all slides")
    if args.animate:
        add_animations(result.output_path, result.output_path, effect=args.animate,
                       trigger="click" if args.animate_on_click else "auto")
        print(f"  • Added '{args.animate}' entrance animations to shapes")

    for w in result.warnings:
        print(f"  ⚠ {w}")
    print(f"\nSaved: {result.output_path}")
    print(f"Plan: {[s['type'] for s in result.plan['slides']]}")
    print(f"Images generated: {result.images_generated}")


if __name__ == "__main__":
    main()
