"""
PadelYara Social Post Generator — Step 1
─────────────────────────────────────────
Loads an AI-generated image, overlays real brand assets and text,
and exports a 1080 × 1350 Instagram-ready PNG.

Usage:
    python tools/social/generate.py
    python tools/social/generate.py --config path/to/other-config.yaml

The script reads all settings from config.yaml (same folder by default).
"""

import argparse
import io
import sys
import textwrap
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

# ── Optional SVG support ──────────────────────────────────────────────────────
# cairosvg converts .svg files to PNG bytes that Pillow can load.
# Install with:  pip install cairosvg
# On Windows you also need the Cairo runtime — see README.md for instructions.
try:
    import cairosvg
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_asset(path: Path, target_width: int) -> Image.Image:
    """
    Load a PNG or SVG file and resize it so its width equals target_width.
    Height is scaled proportionally to keep the original aspect ratio.
    Returns a Pillow Image in RGBA mode (preserves transparency).
    """
    suffix = path.suffix.lower()

    if suffix == ".svg":
        if not SVG_SUPPORT:
            print(
                f"  WARNING: {path.name} is an SVG but cairosvg is not installed.\n"
                "  Install it with:  pip install cairosvg\n"
                "  Skipping this asset."
            )
            return None

        # Render the SVG at the target width so we get full resolution.
        png_bytes = cairosvg.svg2png(
            url=str(path),
            output_width=target_width,
        )
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    else:
        img = Image.open(path).convert("RGBA")
        # Resize to the target width while keeping aspect ratio.
        ratio = target_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((target_width, new_height), Image.LANCZOS)

    return img


def apply_opacity(img: Image.Image, opacity: int) -> Image.Image:
    """
    Return a copy of img with every pixel's alpha multiplied by opacity/255.
    opacity=255 → fully opaque, opacity=0 → invisible.
    """
    # Split into R, G, B, A channels.
    r, g, b, a = img.split()

    # Scale the alpha channel by our opacity factor.
    scale = opacity / 255.0
    a = a.point(lambda px: int(px * scale))

    return Image.merge("RGBA", (r, g, b, a))


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Split `text` into lines that fit within max_width pixels when rendered
    with `font`.  Returns a list of strings, one per line.
    If max_width is 0, returns the text as a single line.
    """
    if max_width == 0:
        return [text]

    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        # getlength measures how wide the string would be in pixels.
        if font.getlength(test) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


# ── Main ──────────────────────────────────────────────────────────────────────

def generate(config_path: Path) -> None:
    """
    Main function.  Reads config_path, composites the post, saves the result.
    """

    # ── 1. Load config ────────────────────────────────────────────────────────
    print(f"Reading config: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # The repo root is two levels above this script (tools/social/generate.py).
    repo_root = Path(__file__).resolve().parent.parent.parent

    # ── 2. Load the AI-generated base image ──────────────────────────────────
    input_path = repo_root / cfg["input_image"]
    print(f"Loading base image: {input_path}")

    if not input_path.exists():
        print(
            f"\nERROR: Input image not found at {input_path}\n"
            "Place your AI-generated image in tools/social/input/ and\n"
            "update 'input_image' in config.yaml."
        )
        sys.exit(1)

    base = Image.open(input_path).convert("RGBA")

    # ── 3. Resize / crop to the target canvas size ────────────────────────────
    canvas_w = cfg["canvas_width"]   # default 1080
    canvas_h = cfg["canvas_height"]  # default 1350

    # Scale so the image covers the entire canvas (like CSS background-size: cover).
    scale = max(canvas_w / base.width, canvas_h / base.height)
    new_w = int(base.width * scale)
    new_h = int(base.height * scale)
    base = base.resize((new_w, new_h), Image.LANCZOS)

    # Crop to exact canvas size, centered.
    left = (new_w - canvas_w) // 2
    top  = (new_h - canvas_h) // 2
    base = base.crop((left, top, left + canvas_w, top + canvas_h))

    print(f"Canvas: {canvas_w} × {canvas_h} px")

    # ── 4. Create the composite canvas ───────────────────────────────────────
    # Work entirely in RGBA so transparency is preserved throughout.
    canvas = Image.new("RGBA", (canvas_w, canvas_h))
    canvas.paste(base, (0, 0))

    # ── 5. Draw the semi-transparent overlay behind the text ─────────────────
    overlay_cfg = cfg.get("text_overlay", {})
    if overlay_cfg.get("enabled", False):
        ox = overlay_cfg["x"]
        oy = overlay_cfg["y"]
        ow = overlay_cfg["width"]
        oh = overlay_cfg["height"]
        oc = tuple(overlay_cfg["color"])  # (R, G, B)
        oo = overlay_cfg["opacity"]       # 0–255

        # Create a solid rectangle of the overlay color.
        overlay_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay_layer)
        draw_overlay.rectangle([ox, oy, ox + ow, oy + oh], fill=(*oc, oo))

        canvas = Image.alpha_composite(canvas, overlay_layer)

    # ── 6. Render text ────────────────────────────────────────────────────────
    text_cfg = cfg["text"]
    font_path = repo_root / text_cfg["font"]
    font_size = text_cfg["font_size"]
    line_spacing = text_cfg.get("line_spacing", 10)
    text_color = tuple(text_cfg["color"]) + (255,)  # add full alpha
    text_x = text_cfg["x"]
    text_y = text_cfg["y"]
    max_width = text_cfg.get("max_width", 0)

    print(f"Loading font: {font_path}")
    font = ImageFont.truetype(str(font_path), font_size)

    # Draw onto a transparent layer so we can composite cleanly.
    text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    # Each entry in cfg["text"]["lines"] is one paragraph / line group.
    cursor_y = text_y
    for raw_line in text_cfg["lines"]:
        # Word-wrap each line if max_width is set.
        wrapped = wrap_text(raw_line, font, max_width)
        for line in wrapped:
            draw.text((text_x, cursor_y), line, font=font, fill=text_color)
            # Advance by the line height + extra spacing.
            line_height = font.getbbox(line)[3] - font.getbbox(line)[1]
            cursor_y += line_height + line_spacing
        # Add a bit of extra space between paragraph groups.
        cursor_y += line_spacing

    canvas = Image.alpha_composite(canvas, text_layer)

    # ── 7. Paste the paw / cat-head signature ────────────────────────────────
    paw_cfg = cfg.get("paw")
    if paw_cfg:
        paw_path = repo_root / paw_cfg["file"]
        print(f"Loading paw asset: {paw_path}")
        paw_img = load_asset(paw_path, paw_cfg["width"])
        if paw_img is not None:
            paw_img = apply_opacity(paw_img, paw_cfg.get("opacity", 255))
            canvas.paste(paw_img, (paw_cfg["x"], paw_cfg["y"]), mask=paw_img)

    # ── 8. Paste the wordmark / lockup ───────────────────────────────────────
    wordmark_cfg = cfg.get("wordmark")
    if wordmark_cfg:
        wm_path = repo_root / wordmark_cfg["file"]
        print(f"Loading wordmark: {wm_path}")
        wm_img = load_asset(wm_path, wordmark_cfg["width"])
        if wm_img is not None:
            wm_img = apply_opacity(wm_img, wordmark_cfg.get("opacity", 255))
            canvas.paste(wm_img, (wordmark_cfg["x"], wordmark_cfg["y"]), mask=wm_img)

    # ── 9. Export ─────────────────────────────────────────────────────────────
    output_path = repo_root / cfg["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to RGB before saving as PNG (removes the RGBA alpha channel,
    # which is fine for a finished social post destined for Instagram).
    final = canvas.convert("RGB")
    final.save(str(output_path), format="PNG", optimize=True)

    print(f"\nDone!  Saved to: {output_path}")
    print(f"Size: {final.width} × {final.height} px")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PadelYara Social Post Generator")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
        help="Path to config.yaml (default: same folder as this script)",
    )
    args = parser.parse_args()
    generate(args.config)
