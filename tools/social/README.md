# PadelYara Social Post Generator

A simple Python tool that takes an AI-generated image and adds real brand assets on top to produce an Instagram-ready post (1080 × 1350 px).

**What it does:**
1. Loads your AI-generated base image
2. Resizes and crops it to 1080 × 1350
3. Adds a semi-transparent dark overlay on the left side (so text is readable)
4. Renders text in the Cinzel font
5. Places the PadelYara wordmark in the lower left
6. Adds the cat-head signature above the wordmark
7. Exports a finished PNG

The tool never touches or recreates the logo files — it only reads and composites them.

---

## Setup

### 1. Install Python dependencies

```bash
pip install Pillow pyyaml cairosvg
```

**About cairosvg:** This is needed to load the SVG brand assets (wordmark, cat head). Without it, only the text will be added — the logo elements will be skipped with a warning.

**Windows — extra step for cairosvg:**
cairosvg needs the Cairo graphics library. The easiest way to get it on Windows:

```
pip install cairosvg
```

If you see an error about a missing DLL, download and install **GTK3 for Windows** from:
https://github.com/nicowillis/cairosvg-windows — or use the Chocolatey package:
```
choco install gtk-runtime
```

If you are on macOS, use:
```
brew install cairo
pip install cairosvg
```

---

## How to run

### 1. Drop your AI-generated image into `brand/social/input/`

Name it `scene.png` (or update `input_image` in `config.yaml`).

### 2. Run the generator from the repo root

```bash
python tools/social/generate.py
```

The finished image is saved to `brand/social/output/post.png`.

### 3. Optional: use a different config file

```bash
python tools/social/generate.py --config tools/social/my-other-config.yaml
```

---

## How to change the text

Open `tools/social/config.yaml` and edit the `text.lines` section:

```yaml
text:
  lines:
    - "Wo spielst du"
    - "heute?"
```

Each entry in `lines` is one piece of text. Add as many lines as you need.

---

## How to change positions and sizes

Everything is controlled by `config.yaml`. No Python knowledge needed.

| Setting | What it does |
|---|---|
| `text.x` / `text.y` | Top-left corner of the text block |
| `text.font_size` | How big the text is (in pixels) |
| `text.line_spacing` | Space between lines |
| `text.max_width` | At what pixel width text wraps to the next line (0 = no wrap) |
| `wordmark.x` / `wordmark.y` | Top-left corner of the wordmark |
| `wordmark.width` | How wide the wordmark is (height scales automatically) |
| `wordmark.opacity` | 0 = invisible, 255 = fully solid |
| `paw.x` / `paw.y` | Position of the cat-head signature |
| `paw.width` | Size of the cat-head signature |
| `paw.opacity` | 0 = invisible, 255 = fully solid |
| `text_overlay.opacity` | How dark the left-side overlay is (0 = off, 90 = subtle) |
| `text_overlay.width` | How far the overlay extends from the left edge |

---

## File structure

```
tools/social/
├── generate.py      ← the script
├── config.yaml      ← all settings (edit this, not the script)
└── README.md

brand/social/
├── input/           ← put your AI images here
│   └── scene.png    ← example name (configured in config.yaml)
└── output/          ← finished posts are saved here
    └── post.png
```

Brand assets used (never modified, only read):

```
brand/
├── CinzelFont/static/Cinzel-Bold.ttf    ← text font
├── lockups/lockup-horizontal-light.svg  ← wordmark
└── logo/logo-transparent-white-only-head.svg  ← cat-head signature
```

---

## Troubleshooting

**"Input image not found"** — check that your image file is in `tools/social/input/` and that `input_image` in `config.yaml` points to it.

**"cairosvg is not installed" warning** — the logo elements are skipped. Install cairosvg (see Setup above).

**Text is cut off** — increase `text.max_width` or reduce `text.font_size` in `config.yaml`.

**Wordmark is too small/large** — adjust `wordmark.width` in `config.yaml`.
