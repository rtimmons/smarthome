#!/usr/bin/env python3
"""
Advanced visual diff generator for printer label regression tests.

Creates intelligent difference visualizations:
- Pixel-level difference highlighting
- Side-by-side overlays with transparency
- Difference heatmaps
- Annotated change regions
"""

import sys
import argparse
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageEnhance


def load_images(baseline_path: Path, diff_path: Path) -> Tuple[Image.Image, Image.Image]:
    """Load and validate baseline and diff images."""
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline image not found: {baseline_path}")
    if not diff_path.exists():
        raise FileNotFoundError(f"Diff image not found: {diff_path}")

    baseline = Image.open(baseline_path).convert("RGBA")
    current = Image.open(diff_path).convert("RGBA")

    # Ensure images are the same size
    if baseline.size != current.size:
        print(f"Warning: Image size mismatch. Baseline: {baseline.size}, Current: {current.size}")
        # Resize current to match baseline
        current = current.resize(baseline.size, Image.Resampling.LANCZOS)

    return baseline, current


def create_difference_mask(
    baseline: Image.Image, current: Image.Image, threshold: int = 10
) -> Image.Image:
    """Create a binary mask highlighting pixel differences."""
    # Convert to RGB for difference calculation
    base_rgb = baseline.convert("RGB")
    curr_rgb = current.convert("RGB")

    # Calculate absolute difference
    diff = ImageChops.difference(base_rgb, curr_rgb)

    # Convert to grayscale and apply threshold
    diff_gray = diff.convert("L")

    # Create binary mask where differences exceed threshold
    mask = diff_gray.point(lambda x: 255 if x > threshold else 0, mode="1")

    return mask


def create_heatmap_overlay(baseline: Image.Image, current: Image.Image) -> Image.Image:
    """Create a heatmap showing intensity of differences."""
    base_rgb = baseline.convert("RGB")
    curr_rgb = current.convert("RGB")

    # Calculate per-channel differences
    diff = ImageChops.difference(base_rgb, curr_rgb)

    # Convert to grayscale to get intensity
    diff_gray = diff.convert("L")

    # Create a simple heatmap by colorizing the grayscale difference
    # Red channel = high intensity differences
    # Green channel = medium intensity differences
    # Blue channel = low intensity differences

    # Create RGB channels for heatmap
    width, height = diff_gray.size
    heatmap = Image.new("RGB", (width, height))

    # Simple color mapping: grayscale intensity -> heat colors
    pixels = list(diff_gray.getdata())
    heatmap_pixels = []

    for intensity in pixels:
        if intensity > 200:  # Very high difference - red
            heatmap_pixels.append((255, 0, 0))
        elif intensity > 150:  # High difference - orange
            heatmap_pixels.append((255, 128, 0))
        elif intensity > 100:  # Medium difference - yellow
            heatmap_pixels.append((255, 255, 0))
        elif intensity > 50:  # Low difference - green
            heatmap_pixels.append((0, 255, 0))
        elif intensity > 10:  # Very low difference - blue
            heatmap_pixels.append((0, 128, 255))
        else:  # No difference - transparent/black
            heatmap_pixels.append((0, 0, 0))

    heatmap.putdata(heatmap_pixels)
    # Convert to RGBA for transparency
    heatmap_rgba = Image.new("RGBA", heatmap.size)

    # Add alpha channel based on intensity
    pixels = list(heatmap.getdata())
    rgba_pixels = []

    for r, g, b in pixels:
        # Calculate intensity from RGB
        intensity = max(r, g, b)
        # Set alpha based on intensity (more intense = more opaque)
        alpha = min(intensity * 2, 200) if intensity > 0 else 0
        rgba_pixels.append((r, g, b, alpha))

    heatmap_rgba.putdata(rgba_pixels)
    return heatmap_rgba


def create_side_by_side_overlay(
    baseline: Image.Image, current: Image.Image, heatmap: Image.Image
) -> Image.Image:
    """Create side-by-side comparison with overlay."""
    width, height = baseline.size

    # Create canvas for side-by-side comparison
    canvas = Image.new("RGBA", (width * 2 + 20, height + 60), (255, 255, 255, 255))

    # Add baseline image
    canvas.paste(baseline, (0, 30))

    # Add current image
    canvas.paste(current, (width + 20, 30))

    # Overlay heatmap on current image with transparency
    overlay_current = Image.alpha_composite(current, heatmap)
    canvas.paste(overlay_current, (width + 20, 30))

    # Add labels
    draw = ImageDraw.Draw(canvas)
    try:
        # Try to use a better font if available
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
    except (OSError, IOError):
        font = ImageFont.load_default()

    draw.text((width // 2 - 30, 5), "EXPECTED", fill=(0, 100, 0, 255), font=font)
    draw.text((width + 20 + width // 2 - 25, 5), "ACTUAL", fill=(200, 0, 0, 255), font=font)

    return canvas


def create_difference_visualization(
    baseline: Image.Image, current: Image.Image
) -> tuple[Image.Image, float]:
    """Create a comprehensive difference visualization."""
    width, height = baseline.size

    # Create difference mask for statistics first
    mask = create_difference_mask(baseline, current)

    # Calculate difference statistics using PIL
    mask_pixels = list(mask.getdata())
    total_pixels = len(mask_pixels)
    different_pixels = sum(1 for pixel in mask_pixels if pixel > 0)
    diff_percentage = (different_pixels / total_pixels) * 100 if total_pixels > 0 else 0.0

    # If no differences, return None to indicate no visualization needed
    if different_pixels == 0:
        return None, 0.0

    # Create heatmap only if there are differences
    heatmap = create_heatmap_overlay(baseline, current)

    # Create main visualization
    main_viz = create_side_by_side_overlay(baseline, current, heatmap)

    # Add difference-only view at the bottom
    diff_only = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    diff_only = Image.alpha_composite(diff_only, heatmap)

    # Expand canvas to include difference view
    final_width = main_viz.width
    final_height = main_viz.height + height + 40
    final_canvas = Image.new("RGBA", (final_width, final_height), (255, 255, 255, 255))

    # Paste main visualization
    final_canvas.paste(main_viz, (0, 0))

    # Paste difference-only view
    final_canvas.paste(diff_only, (final_width // 2 - width // 2, main_viz.height + 20))

    # Add labels and statistics
    draw = ImageDraw.Draw(final_canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except (OSError, IOError):
        font = ImageFont.load_default()
        font_small = font

    # Label for difference view
    draw.text(
        (final_width // 2 - 50, main_viz.height),
        "DIFFERENCES ONLY",
        fill=(100, 0, 100, 255),
        font=font,
    )

    # Statistics
    stats_y = final_height - 15
    stats_text = f"Changed pixels: {different_pixels:,} ({diff_percentage:.2f}%)"
    draw.text((10, stats_y), stats_text, fill=(100, 100, 100, 255), font=font_small)

    return final_canvas, diff_percentage


def main():
    parser = argparse.ArgumentParser(description="Generate advanced visual diff")
    parser.add_argument("baseline", type=Path, help="Path to baseline image")
    parser.add_argument("current", type=Path, help="Path to current image")
    parser.add_argument("output", type=Path, help="Path for output visualization")
    parser.add_argument("--threshold", type=int, default=10, help="Difference threshold (0-255)")

    args = parser.parse_args()

    try:
        baseline, current = load_images(args.baseline, args.current)
        visualization, diff_percentage = create_difference_visualization(baseline, current)

        # If no differences, don't create the enhanced diff file
        if visualization is None:
            print(f"Images are identical (0.00% difference) - no enhanced diff needed")
            sys.exit(0)

        visualization.save(args.output, "PNG")
        print(f"Visual diff saved to: {args.output} ({diff_percentage:.2f}% different)")

    except Exception as e:
        print(f"Error generating visual diff: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
