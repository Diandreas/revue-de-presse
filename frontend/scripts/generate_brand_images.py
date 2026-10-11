"""Génère les images de marque statiques de frontend/public à partir des éléments de la
charte (encre, indigo, surligneur ambre, Fraunces + Inter) — aucune capture d'écran :

- og-image.png (1200 x 630) : aperçu des liens partagés (WhatsApp, LinkedIn, Facebook, X) ;
- apple-touch-icon.png (180 x 180) : icône d'écran d'accueil iOS ;
- favicon.ico (16/32/48) : repli pour les navigateurs et outils qui ignorent favicon.svg.

Usage (depuis la racine du dépôt, Pillow est déjà installé dans le venv du backend) :

    backend/.venv/Scripts/python.exe frontend/scripts/generate_brand_images.py

Les polices viennent de video/presentation/fonts (mêmes fichiers que le film de présentation).
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public"
FONTS = ROOT / "video" / "presentation" / "fonts"

# Charte (frontend/src/index.css).
INK = (11, 16, 32)
BRAND_500 = (99, 102, 241)
BRAND_950 = (30, 27, 75)
AMBER_300 = (252, 211, 77)
AMBER_400 = (251, 191, 36)
SLATE_300 = (203, 213, 225)
SLATE_400 = (148, 163, 184)
SLATE_500 = (100, 116, 139)
SLATE_900 = (15, 23, 42)
PAPER = (255, 253, 248)
WHITE = (255, 255, 255)

SCALE = 2  # rendu en 2x puis réduction : bords lissés.


def font(name, size):
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size * SCALE)


def s(*values):
    """Coordonnées de la maquette (1x) vers le rendu (2x)."""
    return tuple(v * SCALE for v in values) if len(values) > 1 else values[0] * SCALE


def diagonal_gradient(size, start, end):
    """Dégradé linéaire du coin haut-gauche au coin bas-droit (comme le LogoMark SVG)."""
    width, height = size
    vertical = Image.linear_gradient("L").resize((width, height))
    horizontal = Image.linear_gradient("L").rotate(90).resize((width, height))
    ramp = ImageChops.add(vertical, horizontal, scale=2)  # (x + y) / 2
    return Image.composite(Image.new("RGB", size, end), Image.new("RGB", size, start), ramp)


def logo_mark(size, rounded=True):
    """LogoMark (frontend/src/components/Logo.tsx) dessiné sur une grille de 32 unités."""
    unit = size / 32
    mark = diagonal_gradient((size, size), BRAND_500, BRAND_950).convert("RGBA")
    draw = ImageDraw.Draw(mark)
    draw.rounded_rectangle(
        (6.5 * unit, 13.1 * unit, 25.5 * unit, 18.9 * unit), radius=1.6 * unit, fill=AMBER_400
    )
    stroke = round(2.2 * unit)
    lines = [((9, 9.6), (23, 9.6), (255, 255, 255, 217)), ((9, 16), (23, 16), BRAND_950 + (255,)),
             ((9, 22.4), (18, 22.4), (255, 255, 255, 217))]
    overlay = Image.new("RGBA", mark.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for (x1, y1), (x2, y2), color in lines:
        overlay_draw.line((x1 * unit, y1 * unit, x2 * unit, y2 * unit), fill=color, width=stroke)
        for x in (x1, x2):  # extrémités arrondies (stroke-linecap: round)
            r = stroke / 2
            overlay_draw.ellipse((x * unit - r, y1 * unit - r, x * unit + r, y1 * unit + r), fill=color)
    mark = Image.alpha_composite(mark, overlay)
    if rounded:
        mask = Image.new("L", mark.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=8 * unit, fill=255)
        mark.putalpha(mask)
    return mark


def glow(canvas, center, radius, color, strength):
    """Halo radial (fond « ink-gradient » de l'application)."""
    mask = Image.radial_gradient("L").resize((radius * 2, radius * 2))
    mask = ImageChops.invert(mask).point(lambda v: int(v * strength))
    layer = Image.new("RGB", mask.size, color)
    canvas.paste(layer, (center[0] - radius, center[1] - radius), mask)


def rotated_paste(canvas, layer, position, angle):
    rotated = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(rotated, position)


def tag(text, color):
    """Étiquette blanche (« Risque juridique », « Intox potentielle »)."""
    label_font = font("inter-600", 17)
    width = int(label_font.getlength(text)) + s(36)
    layer = Image.new("RGBA", (width + s(24), s(64)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((s(12), s(14), width + s(12), s(58)), radius=s(12), fill=(0, 0, 0, 110))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s(6))))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((s(12), s(10), width + s(12), s(52)), radius=s(12), fill=WHITE)
    draw.ellipse((s(28), s(26), s(38), s(36)), fill=color)
    draw.text((s(46), s(31)), text, font=label_font, fill=color, anchor="lm")
    return layer


def clipping_card():
    """Coupure de presse fictive, passages surlignés (même idée que ClippingIllustration)."""
    width, height = s(420), s(372)
    card = Image.new("RGBA", (width + s(60), height + s(60)), (0, 0, 0, 0))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((s(30), s(40), width + s(30), height + s(40)), radius=s(22), fill=(0, 0, 0, 150))
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(s(18))))
    draw = ImageDraw.Draw(card)
    left, top = s(30), s(30)
    draw.rounded_rectangle((left, top, left + width, top + height), radius=s(22), fill=PAPER)

    pad = s(30)
    x0, x1 = left + pad, left + width - pad
    draw.text((x0, top + s(28)), "Le Quotidien", font=font("fraunces-700", 22), fill=SLATE_900, anchor="lm")
    draw.text((x1, top + s(28)), "ÉCONOMIE · SOCIÉTÉ", font=font("inter-500", 11), fill=SLATE_500, anchor="rm")
    draw.rectangle((x0, top + s(46), x1, top + s(49)), fill=SLATE_900)

    headline = font("fraunces-600", 25)
    for index, line in enumerate(("Nouvelle réglementation :", "ce qui change pour", "les entreprises")):
        draw.text((x0, top + s(66) + index * s(32)), line, font=headline, fill=SLATE_900)

    # Lignes de texte (barres grises) dont certaines sont surlignées par l'IA.
    rows = [
        (1.0, None), (0.62, (191, 219, 254)), (0.9, None), (0.75, (253, 230, 138)),
        (1.0, None), (0.55, (254, 202, 202)), (0.8, None),
    ]
    y = top + s(186)
    for ratio, highlight in rows:
        line_end = x0 + int((x1 - x0) * ratio)
        if highlight:
            draw.rounded_rectangle((x0 - s(3), y - s(6), line_end + s(3), y + s(14)), radius=s(4), fill=highlight)
        draw.rounded_rectangle((x0, y, line_end, y + s(8)), radius=s(4), fill=(203, 213, 225) if not highlight else (100, 116, 139))
        y += s(24)
    return card


def og_image():
    width, height = s(1200), s(630)
    canvas = Image.new("RGB", (width, height), INK)
    glow(canvas, (s(80), s(20)), s(620), BRAND_500, 0.32)
    glow(canvas, (s(1180), s(640)), s(520), AMBER_400, 0.12)

    grid = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    grid_draw = ImageDraw.Draw(grid)
    for x in range(0, width, s(44)):
        grid_draw.line((x, 0, x, height), fill=(255, 255, 255, 13), width=SCALE)
    for y in range(0, height, s(44)):
        grid_draw.line((0, y, width, y), fill=(255, 255, 255, 13), width=SCALE)
    canvas = Image.alpha_composite(canvas.convert("RGBA"), grid)
    draw = ImageDraw.Draw(canvas)

    # Marque.
    canvas.alpha_composite(logo_mark(s(56)), (s(72), s(60)))
    draw.text((s(144), s(70)), "Revue de Presse", font=font("fraunces-600", 30), fill=WHITE, anchor="lt")
    draw.text((s(145), s(106)), "Veille média augmentée par l’IA", font=font("inter-400", 17), fill=SLATE_400, anchor="lt")

    # Accroche : « analysée » en ambre, comme sur la page d'accueil.
    title = font("fraunces-600", 62)
    x, y, line_height = s(72), s(178), s(74)
    draw.text((x, y), "Votre revue de presse,", font=title, fill=WHITE)
    draw.text((x, y + line_height), "analysée", font=title, fill=AMBER_300)
    draw.text((x + int(title.getlength("analysée ")), y + line_height), "en quelques", font=title, fill=WHITE)
    draw.text((x, y + 2 * line_height), "minutes.", font=title, fill=WHITE)

    body = font("inter-400", 22)
    draw.text((x, s(430)), "Photos ou PDF des journaux → revue au format classique,", font=body, fill=SLATE_300)
    draw.text((x, s(462)), "points clés surlignés, export Word et PDF.", font=body, fill=SLATE_300)

    # Pied : essai gratuit + adresse.
    chip_font = font("inter-600", 19)
    chip_text = "Essai gratuit 7 jours"
    chip_width = int(chip_font.getlength(chip_text)) + s(40)
    draw.rounded_rectangle((x, s(522), x + chip_width, s(566)), radius=s(22), fill=BRAND_500)
    draw.text((x + chip_width // 2, s(544)), chip_text, font=chip_font, fill=WHITE, anchor="mm")
    draw.text((x + chip_width + s(22), s(544)), "Tarifs sur devis · presse.mirlab.cloud", font=font("inter-500", 19),
              fill=SLATE_400, anchor="lm")

    # Illustration : coupure surlignée + étiquettes.
    rotated_paste(canvas, clipping_card(), (s(728), s(118)), 3)
    rotated_paste(canvas, tag("Risque juridique", (185, 28, 28)), (s(948), s(92)), -4)
    rotated_paste(canvas, tag("Intox potentielle", (180, 83, 9)), (s(706), s(470)), 4)

    image = canvas.convert("RGB").resize((1200, 630), Image.LANCZOS)
    image.save(PUBLIC / "og-image.png", optimize=True)


def touch_icon():
    # iOS arrondit lui-même les angles : icône pleine, sans coins transparents.
    icon = logo_mark(s(180), rounded=False).convert("RGB").resize((180, 180), Image.LANCZOS)
    icon.save(PUBLIC / "apple-touch-icon.png", optimize=True)


def favicon():
    mark = logo_mark(256)
    mark.save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


if __name__ == "__main__":
    og_image()
    touch_icon()
    favicon()
    for name in ("og-image.png", "apple-touch-icon.png", "favicon.ico"):
        path = PUBLIC / name
        print(f"{path.relative_to(ROOT)} — {path.stat().st_size // 1024} Ko")
