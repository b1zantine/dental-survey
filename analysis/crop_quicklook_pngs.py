"""Crop Quick Look PNG exports to their visible bounds."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops


def visible_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgb_image = image.convert("RGB")
    background = Image.new("RGB", rgb_image.size, rgb_image.getpixel((0, 0)))
    difference = ImageChops.difference(rgb_image, background)
    bbox = difference.getbbox()
    return bbox or (0, 0, image.width, image.height)


def crop_png(source: Path, target: Path, padding: int, max_width: int, dpi: int) -> None:
    image = Image.open(source).convert("RGBA")
    bbox = visible_bbox(image)
    left = max(bbox[0] - padding, 0)
    top = max(bbox[1] - padding, 0)
    right = min(bbox[2] + padding, image.width)
    bottom = min(bbox[3] + padding, image.height)
    cropped = image.crop((left, top, right, bottom))
    if cropped.width > max_width:
        scaled_height = round(cropped.height * (max_width / cropped.width))
        cropped = cropped.resize((max_width, scaled_height), Image.Resampling.LANCZOS)
    target.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(target, dpi=(dpi, dpi))


def main() -> None:
    parser = argparse.ArgumentParser(description="Crop Quick Look SVG thumbnail PNGs.")
    parser.add_argument("--input-dir", required=True, help="Directory containing *.svg.png thumbnails.")
    parser.add_argument("--output-dir", required=True, help="Directory to write cropped *.png files.")
    parser.add_argument("--padding", type=int, default=24, help="Extra padding around the visible chart.")
    parser.add_argument("--max-width", type=int, default=480, help="Maximum output width in pixels.")
    parser.add_argument("--dpi", type=int, default=144, help="Output DPI metadata.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for png_path in sorted(input_dir.glob("*.svg.png")):
        output_name = png_path.name.replace(".svg.png", ".png")
        crop_png(png_path, output_dir / output_name, args.padding, args.max_width, args.dpi)


if __name__ == "__main__":
    main()
