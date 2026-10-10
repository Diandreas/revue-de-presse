# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""Crops and right-sizes the REAL captures for the film (presentation/assets/film/). Nothing is
drawn here: every output is a crop / resize of a screenshot of the running app, of the demo pages
or of the exported PDF, so the film loads light images (6 render workers decode all of them).

    uv run tools/prep_assets.py      (from video/)
"""
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "presentation"
APP = ROOT / "assets" / "app"
OUT = ROOT / "assets" / "film"
OUT.mkdir(parents=True, exist_ok=True)


def save(im, name, *, max_w=None, max_h=None, jpeg=False):
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if max_h and im.height > max_h:
        im = im.resize((round(im.width * max_h / im.height), max_h), Image.LANCZOS)
    path = OUT / name
    if jpeg:
        im.convert("RGB").save(path, quality=90, optimize=True)
    else:
        im.save(path, optimize=True)
    print(f"{name:34s} {im.width}x{im.height}")
    return im


def trim(im, bg=None, tol=24, pad=10):
    """Crop to the ink: pixels that differ from the background colour (top-left by default)."""
    a = np.asarray(im.convert("RGB")).astype(int)
    bgc = np.array(bg if bg else a[2, 2])
    mask = np.abs(a - bgc).max(axis=2) > tol
    ys, xs = np.nonzero(mask)
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad + 1, im.width), min(ys.max() + pad + 1, im.height))
    return im.crop(box)


# ---- the 9 demo pages (inputs the user photographed), in upload order
for p in sorted((ROOT / "assets" / "pages").glob("*.jpg")):
    save(Image.open(p), f"page_{p.stem[:2]}.jpg", max_h=1000, jpeg=True)

# ---- upload: phone screen, dropzone, documents grid, launch button (desktop @2x)
save(Image.open(APP / "m_upload_filled.png"), "m_upload.png", max_h=1300)
full = Image.open(APP / "upload_filled_full.png")
save(full.crop((640, 420, 2096, 1066)), "upload_dropzone.png")
save(full.crop((640, 1092, 2096, 1900)), "upload_docs.png")
save(full.crop((2160, 884, 2760, 1000)), "upload_launch.png")
save(full.crop((576, 0, 2880, 1800)), "upload_page.jpg", max_w=1800, jpeg=True)

# ---- progress card timelapse (real frames of the analysis, every other frame)
frames = sorted((APP / "progress").glob("*.jpg"))
kept = []
for k, f in enumerate(frames):
    if k % 2 and k != len(frames) - 1:
        continue
    im = Image.open(f).crop((650, 386, 2806, 1497))
    save(im, f"progress_{len(kept):02d}.jpg", max_w=1500, jpeg=True)
    kept.append(f.stem)
(OUT / "progress.json").write_text(json.dumps({"frames": kept}, indent=0))

# ---- the review
save(Image.open(APP / "review_article.png"), "review_article.png", max_w=1336)
save(Image.open(APP / "el" / "masthead.png"), "masthead.png")
for i in range(3):
    save(Image.open(APP / "el" / f"banner_{i}.png"), f"banner_{i}.png")
names = json.loads((APP / "el" / "names.json").read_text(encoding="utf-8"))
for i, name in enumerate(names):
    save(trim(Image.open(APP / "el" / f"name_{i}.png"), pad=6), f"name_{i}.png")
(OUT / "names.json").write_text(json.dumps(names, ensure_ascii=False, indent=0), encoding="utf-8")
save(Image.open(APP / "el" / "notice_0.png"), "notice_0.png", max_w=1400)
mr = Image.open(APP / "m_review_full.png")
save(mr.crop((0, 0, mr.width, min(mr.height, 5600))), "m_review.jpg", max_w=1000, jpeg=True)

# ---- key points
for n in ("hl_risque_detournement", "hl_intox_video", "hl_concurrent_transcam", "hl_important_cacao"):
    save(Image.open(APP / "detail" / f"{n}.png"), f"{n}.png")
save(Image.open(APP / "el" / "chips.png"), "chips.png")

# ---- export
save(Image.open(APP / "el" / "actions.png"), "actions.png")
for i in (1, 2, 3):
    save(Image.open(APP / "pdf" / f"p-{i}.png"), f"pdf_{i}.jpg", max_h=1150, jpeg=True)

# ---- team, categories, trial badge
save(Image.open(APP / "el" / "team_members.png"), "team_members.png", max_w=1600)
save(Image.open(APP / "el" / "cat_custom.png"), "cat_custom.png")
save(Image.open(APP / "el" / "cat_defaults.png"), "cat_defaults.png", max_w=1800)
save(Image.open(APP / "el" / "badge_trial.png"), "badge_trial.png")

# ---- fonts (the site's own Fraunces + Inter files, gathered from the live site)
fonts = ROOT / "fonts"
fonts.mkdir(exist_ok=True)
for src in (ROOT / "assets" / "fonts").glob("*.ttf"):
    family, weight = src.stem.split("-")[:2]
    shutil.copy(src, fonts / f"{family}-{weight}.ttf")
print("fonts:", sorted(p.name for p in fonts.glob("*.ttf")))
