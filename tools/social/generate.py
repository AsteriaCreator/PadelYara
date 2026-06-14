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
import re
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

# ── Optional SVG support ──────────────────────────────────────────────────────
# cairosvg converts .svg files to PNG bytes that Pillow can load.
# Install with:  pip install cairosvg
try:
    import cairosvg
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_asset(path: Path, target_width: int) -> Image.Image:
    """
    Load a PNG or SVG file, resize to target_width (height scales proportionally).
    Returns RGBA Pillow Image.
    """
    suffix = path.suffix.lower()

    if suffix == ".svg":
        if not SVG_SUPPORT:
            print(f"  WARNING: {path.name} is SVG but cairosvg is not installed. Skipping.")
            return None

        # Strip Inkscape white background <rect> so the asset composites cleanly.
        svg_text = path.read_text(encoding="utf-8")
        svg_text = re.sub(
            r'<rect[^>]*fill\s*=\s*["\']#(?:fff(?:fff)?|ffffff)["\'][^>]*/?>',
            '',
            svg_text,
            flags=re.IGNORECASE,
        )
        png_bytes = cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), output_width=target_width)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    else:
        img = Image.open(path).convert("RGBA")
        ratio = target_width / img.width
        return img.resize((target_width, int(img.height * ratio)), Image.LANCZOS)


def apply_opacity(img: Image.Image, opacity: int) -> Image.Image:
    """Scale every pixel's alpha by opacity/255."""
    r, g, b, a = img.split()
    a = a.point(lambda px: int(px * opacity / 255.0))
    return Image.merge("RGBA", (r, g, b, a))


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    if max_width == 0 or not text.strip():
        return [text] if text else []

    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if font.getlength(test) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def paste_asset(canvas, img, x, y):
    """Paste an RGBA image onto canvas at (x, y), using its alpha as mask."""
    canvas.paste(img, (x, y), mask=img)


def recolor_asset(img: Image.Image, color: tuple) -> Image.Image:
    """Replace all visible pixels with `color` (R,G,B), keeping the original alpha."""
    img = img.convert("RGBA")
    _, _, _, a = img.split()
    flat = Image.new("RGBA", img.size, (*color, 255))
    flat.putalpha(a)
    return flat


def scale_to_height(img: Image.Image, target_height: int) -> Image.Image:
    """Scale image so its height equals target_height, width proportional."""
    ratio = target_height / img.height
    return img.resize((int(img.width * ratio), target_height), Image.LANCZOS)


# ── Main ──────────────────────────────────────────────────────────────────────

def generate(config_path: Path) -> None:
    print(f"Reading config: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    repo_root = Path(__file__).resolve().parent.parent.parent

    # ── 1. Load + crop base image ─────────────────────────────────────────────
    input_path = repo_root / cfg["input_image"]
    print(f"Loading base image: {input_path}")
    if not input_path.exists():
        print(f"\nERROR: Input image not found at {input_path}")
        sys.exit(1)

    base = Image.open(input_path).convert("RGBA")
    canvas_w, canvas_h = cfg["canvas_width"], cfg["canvas_height"]

    scale = max(canvas_w / base.width, canvas_h / base.height)
    nw, nh = int(base.width * scale), int(base.height * scale)
    base = base.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - canvas_w) // 2, (nh - canvas_h) // 2
    base = base.crop((left, top, left + canvas_w, top + canvas_h))

    print(f"Canvas: {canvas_w} x {canvas_h} px")
    canvas = Image.new("RGBA", (canvas_w, canvas_h))
    canvas.paste(base, (0, 0))

    # ── 2. Header bar (dark band at top with lockup inside) ───────────────────
    # This anchors the brand and makes the text feel part of the image.
    header_cfg = cfg.get("header_bar", {})
    if header_cfg.get("enabled"):
        bar_h     = header_cfg["height"]
        bar_color = tuple(header_cfg["color"])
        bar_op    = header_cfg["opacity"]

        bar_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        ImageDraw.Draw(bar_layer).rectangle([0, 0, canvas_w, bar_h], fill=(*bar_color, bar_op))
        canvas = Image.alpha_composite(canvas, bar_layer)

        # Lockup inside the header bar
        lk_cfg = header_cfg.get("lockup")
        if lk_cfg:
            lk_path = repo_root / lk_cfg["file"]
            print(f"Loading header lockup: {lk_path}")
            lk_img = load_asset(lk_path, lk_cfg["width"])
            if lk_img:
                lk_img = apply_opacity(lk_img, lk_cfg.get("opacity", 255))
                paste_asset(canvas, lk_img, lk_cfg["x"], lk_cfg["y"])

    # ── 3. Optional left-column text overlay (subtle background behind text) ──
    overlay_cfg = cfg.get("text_overlay", {})
    if overlay_cfg.get("enabled"):
        oc = tuple(overlay_cfg["color"])
        oo = overlay_cfg["opacity"]
        ol = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        ImageDraw.Draw(ol).rectangle(
            [overlay_cfg["x"], overlay_cfg["y"],
             overlay_cfg["x"] + overlay_cfg["width"],
             overlay_cfg["y"] + overlay_cfg["height"]],
            fill=(*oc, oo)
        )
        canvas = Image.alpha_composite(canvas, ol)

    # ── 4. Render text ────────────────────────────────────────────────────────
    text_cfg = cfg["text"]
    font_path = repo_root / text_cfg["font"]
    font_size = text_cfg["font_size"]
    line_spacing = text_cfg.get("line_spacing", 10)
    # Default color for all lines (can be overridden per line — see below)
    default_color = tuple(text_cfg["color"]) + (255,)
    text_x = text_cfg["x"]
    text_y = text_cfg["y"]
    max_width = text_cfg.get("max_width", 0)

    print(f"Loading font: {font_path}")
    font = ImageFont.truetype(str(font_path), font_size)

    text_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    cursor_y = text_y
    for raw_item in text_cfg["lines"]:
        # Each line can be either a plain string, or a dict with:
        #   {text: "...", color: [R, G, B]}
        # This allows per-line accent colors (e.g. brand yellow-green).
        if isinstance(raw_item, dict):
            raw_line  = str(raw_item.get("text", ""))
            clr_list  = raw_item.get("color")
            line_color = tuple(clr_list) + (255,) if clr_list else default_color
        else:
            raw_line   = str(raw_item) if raw_item is not None else ""
            line_color = default_color

        if not raw_line.strip():
            # Blank line — just add vertical space.
            cursor_y += int(font_size * 0.8)
            continue

        wrapped = wrap_text(raw_line, font, max_width)
        for line in wrapped:
            draw.text((text_x, cursor_y), line, font=font, fill=line_color)
            line_height = font.getbbox(line)[3] - font.getbbox(line)[1]
            cursor_y += line_height + line_spacing
        cursor_y += line_spacing  # extra gap between paragraph groups

    canvas = Image.alpha_composite(canvas, text_layer)

    # ── 5. Paw / cat-head signature ───────────────────────────────────────────
    paw_cfg = cfg.get("paw")
    if paw_cfg:
        paw_path = repo_root / paw_cfg["file"]
        print(f"Loading paw: {paw_path}")
        paw_img = load_asset(paw_path, paw_cfg["width"])
        if paw_img:
            paw_img = apply_opacity(paw_img, paw_cfg.get("opacity", 255))
            paste_asset(canvas, paw_img, paw_cfg["x"], paw_cfg["y"])

    # ── 6. Signature line: "— " + name image + paw image ────────────────────────
    # Renders all three elements inline on the same baseline.
    sig_cfg = cfg.get("signature")
    if sig_cfg and sig_cfg.get("enabled"):
        sig_x   = sig_cfg["x"]
        sig_y   = sig_cfg["y"]
        sig_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw_sig  = ImageDraw.Draw(sig_layer)
        cursor_x  = sig_x

        # "— " dash prefix in Cinzel
        dash_cfg   = sig_cfg.get("dash", {})
        dash_text  = dash_cfg.get("text", "—")
        dash_color = tuple(dash_cfg.get("color", text_cfg["color"])) + (255,)
        draw_sig.text((cursor_x, sig_y), dash_text + " ", font=font, fill=dash_color)
        cursor_x += int(font.getlength(dash_text + " "))

        # Name image (e.g. yara.png) — scaled to match text cap height
        name_cfg = sig_cfg.get("name")
        if name_cfg:
            name_path = repo_root / name_cfg["file"]
            print(f"Loading signature name: {name_path}")
            name_img  = Image.open(name_path).convert("RGBA")
            name_color = tuple(name_cfg.get("color", [192, 192, 200]))
            name_img  = recolor_asset(name_img, name_color)
            name_h    = name_cfg.get("height", font_size)
            name_img  = scale_to_height(name_img, name_h)
            name_img  = apply_opacity(name_img, name_cfg.get("opacity", 255))
            line_h    = font.getbbox(dash_text)[3] - font.getbbox(dash_text)[1]
            y_name    = sig_y + max(0, (line_h - name_h) // 2)
            paste_asset(sig_layer, name_img, cursor_x, y_name)
            cursor_x += name_img.width + name_cfg.get("gap_after", 14)

        # Paw image — same color and height, vertically centered
        paw_sig_cfg = sig_cfg.get("paw")
        if paw_sig_cfg:
            paw_path  = repo_root / paw_sig_cfg["file"]
            print(f"Loading signature paw: {paw_path}")
            paw_img   = Image.open(paw_path).convert("RGBA")
            paw_color = tuple(paw_sig_cfg.get("color", [192, 192, 200]))
            paw_img   = recolor_asset(paw_img, paw_color)
            paw_h     = paw_sig_cfg.get("height", font_size)
            paw_img   = scale_to_height(paw_img, paw_h)
            paw_img   = apply_opacity(paw_img, paw_sig_cfg.get("opacity", 220))
            line_h    = font.getbbox(dash_text)[3] - font.getbbox(dash_text)[1]
            y_paw     = sig_y + max(0, (line_h - paw_h) // 2)
            paste_asset(sig_layer, paw_img, cursor_x, y_paw)

        canvas = Image.alpha_composite(canvas, sig_layer)

    # ── 8. Bottom wordmark (optional — disabled when using header bar) ─────────
    wordmark_cfg = cfg.get("wordmark")
    if wordmark_cfg:
        wm_path = repo_root / wordmark_cfg["file"]
        print(f"Loading wordmark: {wm_path}")
        wm_img = load_asset(wm_path, wordmark_cfg["width"])
        if wm_img:
            wm_img = apply_opacity(wm_img, wordmark_cfg.get("opacity", 255))
            paste_asset(canvas, wm_img, wordmark_cfg["x"], wordmark_cfg["y"])

    # ── 9. Export ─────────────────────────────────────────────────────────────
    # Resolve the output directory, then auto-number the file.
    # When running from a git worktree the worktree root and the main repo root
    # can differ — check for a sibling repo at the same relative depth and
    # write there too so the file lands where the user expects it.
    if "output_dir" in cfg:
        out_dir = repo_root / cfg["output_dir"]
    else:
        # Legacy: output_path points to a specific file; derive its directory.
        out_dir = (repo_root / cfg["output_path"]).parent

    out_dir.mkdir(parents=True, exist_ok=True)

    # Also look for the same folder in the main working tree (two levels up from
    # a .claude/worktrees/<repo>/<branch>/ path) so the output is visible there.
    extra_dirs = []
    worktrees_marker = out_dir.parts
    try:
        idx = list(worktrees_marker).index(".claude")
        main_root = Path(*worktrees_marker[:idx])
        extra_out = main_root / cfg.get("output_dir", cfg.get("output_path", "brand/social/output"))
        if "output_path" in cfg:
            extra_out = extra_out.parent
        if extra_out != out_dir and main_root.exists():
            extra_out.mkdir(parents=True, exist_ok=True)
            extra_dirs.append(extra_out)
    except (ValueError, TypeError):
        pass

    # Find the next free number across all candidate directories.
    all_existing = sorted(out_dir.glob("post_*.png"))
    for d in extra_dirs:
        all_existing += list(d.glob("post_*.png"))
    next_num = 1
    if all_existing:
        nums = []
        for p in all_existing:
            try:
                nums.append(int(p.stem.split("_")[-1]))
            except ValueError:
                pass
        if nums:
            next_num = max(nums) + 1

    filename = f"post_{next_num:03d}.png" if "output_dir" in cfg else Path(cfg["output_path"]).name
    output_path = out_dir / filename

    final = canvas.convert("RGB")
    final.save(str(output_path), format="PNG", optimize=True)
    print(f"\nDone! Saved to: {output_path}  ({final.width} x {final.height} px)")
    for d in extra_dirs:
        dest = d / filename
        import shutil
        shutil.copy2(str(output_path), str(dest))
        print(f"      Also copied to: {dest}")


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
