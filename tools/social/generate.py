"""
PadelYara Social Post Generator
────────────────────────────────
Loads an AI-generated image, overlays real brand assets and text,
and exports a 1080 × 1350 Instagram-ready PNG.

Optionally posts directly to Instagram via Composio.

Usage:
    python tools/social/generate.py               # generate only
    python tools/social/generate.py --post        # generate + post
    python tools/social/generate.py --config path/to/other-config.yaml --post

Requires for posting:
    pip install composio-core
    COMPOSIO_API_KEY in .env
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


def draw_paw(size: int, color: tuple) -> Image.Image:
    """
    Draw a paw print at `size` pixels tall.
    Shape: four small toe beans in an arc + one large central pad beneath.
    Returns an RGBA image with transparent background.
    """
    w = int(size * 0.90)
    img = Image.new("RGBA", (w, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (*color, 255)

    # Main pad — wide oval in the lower half
    pw, ph = int(w * 0.56), int(size * 0.46)
    px = (w - pw) // 2
    py = size - ph - int(size * 0.06)
    d.ellipse([px, py, px + pw, py + ph], fill=c)

    # Four toe beans — small ovals arcing above the pad
    tw, th = int(w * 0.22), int(size * 0.23)
    toes = [
        (int(w * 0.03), int(size * 0.28)),   # far left
        (int(w * 0.27), int(size * 0.08)),   # centre-left
        (int(w * 0.51), int(size * 0.08)),   # centre-right
        (int(w * 0.72), int(size * 0.28)),   # far right
    ]
    for tx, ty in toes:
        d.ellipse([tx, ty, tx + tw, ty + th], fill=c)

    return img


def scale_to_height(img: Image.Image, target_height: int) -> Image.Image:
    """Scale image so its height equals target_height, width proportional."""
    ratio = target_height / img.height
    return img.resize((int(img.width * ratio), target_height), Image.LANCZOS)


def crop_to_content(img: Image.Image) -> Image.Image:
    """Trim transparent/empty border so the asset fills its bounding box."""
    bbox = img.getbbox()   # returns (left, upper, right, lower) of non-zero pixels
    if bbox:
        return img.crop(bbox)
    return img


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

        # Measure the font cap-height once so we can vertically centre everything
        dash_cfg   = sig_cfg.get("dash", {})
        dash_text  = dash_cfg.get("text", "—")
        dash_color = tuple(dash_cfg.get("color", text_cfg["color"])) + (255,)
        bbox       = font.getbbox("YARA")
        cap_h      = bbox[3] - bbox[1]   # actual rendered height of capital letters
        cap_top    = bbox[1]              # ascender offset from the draw origin

        # Draw the dash only if non-empty
        if dash_text:
            draw_sig.text((cursor_x, sig_y), dash_text + " ", font=font, fill=dash_color)
            cursor_x += int(font.getlength(dash_text + " "))

        # "YARA" rendered directly in Cinzel — same font, same size, silver
        name_cfg   = sig_cfg.get("name", {})
        name_text  = name_cfg.get("text", "YARA")
        name_color = tuple(name_cfg.get("color", [200, 200, 210])) + (255,)
        draw_sig.text((cursor_x, sig_y), name_text, font=font, fill=name_color)
        cursor_x += int(font.getlength(name_text)) + name_cfg.get("gap_after", 18)

        # Paw — use file if provided, otherwise fall back to PIL-drawn shape
        paw_sig_cfg = sig_cfg.get("paw", {})
        paw_color   = tuple(paw_sig_cfg.get("color", [200, 200, 210]))
        paw_file    = paw_sig_cfg.get("file")
        if paw_file:
            paw_path = repo_root / paw_file
            print(f"Loading signature paw: {paw_path}")
            paw_img  = Image.open(paw_path).convert("RGBA")
            paw_img  = crop_to_content(paw_img)   # trim empty padding first
            paw_img  = recolor_asset(paw_img, paw_color)
            # Scale by width so the paw reads as the same visual weight as the text.
            paw_w    = paw_sig_cfg.get("width", cap_h)
            ratio    = paw_w / paw_img.width
            paw_img  = paw_img.resize((paw_w, int(paw_img.height * ratio)), Image.LANCZOS)
        else:
            paw_h   = paw_sig_cfg.get("height", cap_h)
            paw_img = draw_paw(paw_h, paw_color)

        paw_img = apply_opacity(paw_img, paw_sig_cfg.get("opacity", 220))
        # Align paw bottom with text baseline, then lift by `rise` pixels
        rise  = paw_sig_cfg.get("rise", 0)
        y_paw = sig_y + cap_top + cap_h - paw_img.height - rise
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

    # ── 9. Footer text (brand name + URL) ────────────────────────────────────
    footer_cfg = cfg.get("footer")
    if footer_cfg:
        footer_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        footer_draw  = ImageDraw.Draw(footer_layer)
        footer_font_path = repo_root / footer_cfg["font"]
        footer_x = footer_cfg["x"]
        for line in footer_cfg.get("lines", []):
            f = ImageFont.truetype(str(footer_font_path), line["font_size"])
            footer_draw.text(
                (footer_x, line["y"]),
                line["text"],
                font=f,
                fill=tuple(line["color"]) + (255,),
            )
        canvas = Image.alpha_composite(canvas, footer_layer)

    # ── 10. Export ────────────────────────────────────────────────────────────
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

    return output_path, cfg


# ── Instagram posting via Composio ────────────────────────────────────────────

def post_to_instagram(image_path: Path, cfg: dict) -> None:
    """
    Post the generated image to Instagram via the Composio SDK.
    Requires:
      - pip install composio-core
      - COMPOSIO_API_KEY in environment / .env
    """
    try:
        from composio import ComposioToolSet
    except ImportError:
        print("\nERROR: composio-core is not installed.")
        print("  Run:  pip install composio-core")
        sys.exit(1)

    ig_cfg  = cfg.get("instagram", {})
    user_id = ig_cfg.get("user_id", "")
    if not user_id:
        print("\nERROR: instagram.user_id is missing in config.yaml")
        sys.exit(1)

    # Build caption: main text + optional hashtags
    post_cfg = cfg.get("post", {})
    caption  = post_cfg.get("caption", "")
    hashtags = post_cfg.get("hashtags", [])
    if hashtags:
        caption = caption.rstrip() + "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

    print(f"\nPosting to Instagram @padelyara …")
    print(f"  Image : {image_path.name}")
    print(f"  Caption:\n{caption}\n")

    # Load env vars from .env if present
    env_path = image_path.parents[3] / ".env"   # repo root
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                import os
                os.environ.setdefault(k.strip(), v.strip())

    toolset = ComposioToolSet()

    # Step 1: create media container (Composio uploads the local file to a
    # temporary public URL that Instagram can fetch)
    with open(image_path, "rb") as f:
        create_result = toolset.execute_action(
            action="INSTAGRAM_POST_IG_USER_MEDIA",
            params={
                "ig_user_id": user_id,
                "caption": caption,
                "image_file": {
                    "name": image_path.name,
                    "mimetype": "image/png",
                    "content": f,
                },
            },
        )

    print(f"  Container result: {create_result}")

    container_id = None
    if isinstance(create_result, dict):
        container_id = (
            create_result.get("data", {}).get("id")
            or create_result.get("id")
        )

    if not container_id:
        print("\nERROR: Could not get container ID from Composio. See result above.")
        sys.exit(1)

    print(f"  Container ID: {container_id}")

    # Step 2: publish
    publish_result = toolset.execute_action(
        action="INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
        params={
            "ig_user_id": user_id,
            "creation_id": container_id,
        },
    )

    print(f"  Publish result: {publish_result}")
    media_id = None
    if isinstance(publish_result, dict):
        media_id = (
            publish_result.get("data", {}).get("id")
            or publish_result.get("id")
        )

    if media_id:
        print(f"\n✓ Posted! Media ID: {media_id}")
    else:
        print("\nWarning: no media ID returned — check Instagram to confirm.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PadelYara Social Post Generator")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).parent / "config.yaml",
        help="Path to config.yaml (default: same folder as this script)",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Post the generated image to Instagram via Composio after generating",
    )
    args = parser.parse_args()
    result = generate(args.config)
    if args.post and result:
        image_path, cfg = result
        post_to_instagram(image_path, cfg)
