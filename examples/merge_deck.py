"""CLI for {{placeholder}} merge templates.

    # 1. convert a registered template into a {{placeholder}} template (offline)
    python examples/merge_deck.py make sdg_green

    # 2a. render with your own data file (offline)
    python examples/merge_deck.py render library/sdg_green_merge.pptx data.json -o out/deck.pptx

    # 2b. or let GPT-4o produce the data from a brief, then render
    python examples/merge_deck.py generate library/sdg_green_merge.pptx \
        "Báo cáo tiến độ SDG của Việt Nam" -o out/deck.pptx --with-images
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slide_skills.merge_template import (
    generate_merge_data, load_schema, make_placeholder_template, render_placeholders,
)


def cmd_make(args):
    src = Path(args.template)
    if not src.suffix:
        src = Path("library") / f"{args.template}.pptx"
    if not src.is_file():
        sys.exit(f"template not found: {src}")
    dst = src.with_name(f"{src.stem}_merge.pptx")
    schema = make_placeholder_template(src, dst)
    print(f"Merge template: {dst}")
    print(f"Schema:         {dst.with_suffix('.schema.json')}")
    print(f"\n{len(schema['text'])} text placeholders, "
          f"{len(schema['images'])} image placeholders. Examples:")
    for name, meta in list(schema["text"].items())[:8]:
        shape = f"list[{meta['paragraphs']}]" if meta["paragraphs"] > 1 else "string"
        print(f"  {{{{{name}}}}}  {shape}, ≤{meta['max_chars']} chars")
    for name in list(schema["images"])[:4]:
        print(f"  {{{{{name}}}}}  image")


def cmd_render(args):
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    unfilled = render_placeholders(args.template, data, args.output)
    print(f"Saved: {args.output}")
    if unfilled:
        print(f"⚠ {len(unfilled)} placeholders had no data (left empty): "
              f"{', '.join(unfilled[:10])}")


def cmd_generate(args):
    print("Generating data with GPT-4o…")
    text_data, image_prompts = generate_merge_data(
        args.template, args.brief, language=args.language)

    data_path = Path(args.output).with_suffix(".data.json")
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(
        {"text": text_data, "image_prompts": image_prompts},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Data saved to {data_path} (edit + re-render any time)")

    images = {}
    if args.with_images and image_prompts:
        from slide_skills import generate_image
        schema = load_schema(args.template)
        print(f"Rendering {len(image_prompts)} images with DALL-E…")
        for name, prompt in image_prompts.items():
            try:
                images[name] = generate_image(
                    prompt, schema["images"][name]["aspect_ratio"])
                print(f"  ✓ {name}")
            except Exception as exc:
                print(f"  ⚠ {name}: {exc}")

    unfilled = render_placeholders(args.template, text_data, args.output, images=images)
    print(f"Saved: {args.output}")
    if unfilled:
        print(f"⚠ unfilled: {', '.join(unfilled[:10])}")


def main():
    ap = argparse.ArgumentParser(description="{{placeholder}} merge-template workflow")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("make", help="Convert a template into a {{placeholder}} merge template")
    p.add_argument("template", help="Library name (sdg_green) or .pptx path")
    p.set_defaults(func=cmd_make)

    p = sub.add_parser("render", help="Render a merge template with a JSON data file")
    p.add_argument("template")
    p.add_argument("data", help='JSON: {"<placeholder>": "value" | ["a","b"]}')
    p.add_argument("-o", "--output", default="out/merged.pptx")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("generate", help="GPT-4o fills the schema, then render")
    p.add_argument("template")
    p.add_argument("brief")
    p.add_argument("-o", "--output", default="out/merged.pptx")
    p.add_argument("--language", default=None)
    p.add_argument("--with-images", action="store_true")
    p.set_defaults(func=cmd_generate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
