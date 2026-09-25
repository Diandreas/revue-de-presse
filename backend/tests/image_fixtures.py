"""Génère une image réellement valide en mémoire pour les tests d'ingestion de photos,
sans versionner de binaire dans le repo."""
import io

from PIL import Image, ImageDraw


def make_image_bytes(text="Coupure de presse - Cameroun Tribune", size=(700, 300), fmt="PNG"):
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), text, fill="black")
    draw.text((20, 60), "Le gouvernement annonce une nouvelle loi.", fill="black")
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()
