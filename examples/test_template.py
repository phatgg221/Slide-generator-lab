"""CLI: dry-run test of a registered template — no API key, no cost.

Fills every fillable text box with a visible marker (slide type, role, char
budget) and every image placeholder with a labeled color block, then saves a
test deck you can open to SEE what the generator will control.

Usage:
    python examples/test_template.py sdg_green
    python examples/test_template.py library/sdg_green.pptx -o out/check.pptx
"""

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw

from slide_skills import fill_template, parse_template
from slide_skills.assembler import load_library_meta
from slide_skills.content_generator import GeneratedDeckContent, GeneratedSlideContent

COLORS = [(46, 134, 171), (214, 122, 44), (106, 153, 78), (155, 81, 122)]


def placeholder_png(width, height, label, color):
    img = Image.new("RGB", (max(width, 64), max(height, 64)), color)
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), f"IMAGE {label}", fill="white")
    draw.rectangle([0, 0, img.width - 1, img.height - 1], outline="white", width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def marker_text(slide_type, element):
    base = f"{slide_type}|{element.role} {element.max_chars}ch"
    if element.n_paragraphs > 1:
        lines = [f"{base} L{i + 1}" for i in range(element.n_paragraphs)]
        return "\n".join(lines)
    return base[: max(element.max_chars, 8)]


def main():
    ap = argparse.ArgumentParser(description="Visual dry-run of a template (offline)")
    ap.add_argument("template", help="Library template name (e.g. sdg_green) or .pptx path")
    ap.add_argument("-o", "--output", default=None)
    args = ap.parse_args()

    path = Path(args.template)
    if not path.suffix:
        path = Path("library") / f"{args.template}.pptx"
    if not path.is_file():
        ap.error(f"template not found: {path}")

    types, _ = load_library_meta(path)
    spec = parse_template(path)

    content = GeneratedDeckContent()
    images = {}
    n_text = n_img = 0
    for slide_type, s in zip(types, spec.slides):
        slide_content = GeneratedSlideContent(index=s.index)
        for t in s.texts:
            slide_content.texts[t.shape_id] = marker_text(slide_type, t)
            n_text += 1
        for i, img in enumerate(s.images):
            images[(s.index, img.shape_id)] = placeholder_png(
                img.width_px, img.height_px,
                f"{s.index}.{img.shape_id} ar{img.aspect_ratio}",
                COLORS[i % len(COLORS)],
            )
            n_img += 1
        content.slides.append(slide_content)

    output = args.output or f"out/test_{path.stem}.pptx"
    fill_template(path, content, output, images=images, spec=spec)

    print(f"Test deck: {output}")
    print(f"Marked {n_text} text boxes and {n_img} image placeholders "
          f"across {len(spec.slides)} slides.")
    print()
    print("Open it and check each slide:")
    print("  - marked text = will be AI-written (label shows type|role + budget)")
    print("  - colored blocks = will be DALL-E images")
    print("  - anything unmarked = stays exactly as designed")
    skips = [t for t in types if t.startswith('_')]
    if skips:
        print(f"  - {len(skips)} slides are _skip types (never used in generation)")


if __name__ == "__main__":
    main()
