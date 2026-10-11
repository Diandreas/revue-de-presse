"""Génération d'un PDF minimal mais réellement valide (texte natif extractible par
pdfplumber), pour les tests qui exercent l'extraction/le pipeline sans dépendre d'un
fichier binaire versionné dans le repo."""


def make_minimal_pdf_bytes(lines):
    content_stream = "BT /F1 14 Tf 50 750 Td 16 TL\n"
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content_stream += f"({escaped}) Tj T*\n"
    content_stream += "ET"

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream_bytes = content_stream.encode("latin-1")
    objects.append(f"<< /Length {len(stream_bytes)} >>\nstream\n{content_stream}\nendstream")

    parts = [b"%PDF-1.4\n"]
    offsets = []
    offset = len(parts[0])
    for i, obj in enumerate(objects, start=1):
        offsets.append(offset)
        chunk = f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
        parts.append(chunk)
        offset += len(chunk)

    xref_offset = offset
    n = len(objects) + 1
    xref = [f"xref\n0 {n}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))
    trailer = (
        f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1")
    )

    return b"".join(parts) + b"".join(xref) + trailer


def make_multipage_pdf_bytes(pages):
    """PDF de len(pages) pages ; chaque élément est la liste des lignes de la page (liste
    vide = page sans texte natif, comme une page scannée)."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        stream = "BT /F1 14 Tf 50 750 Td 16 TL\n"
        for line in lines:
            escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            stream += f"({escaped}) Tj T*\n"
        stream += "ET"
        objects.append(f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream")
        content_ref = len(objects)
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_ref} 0 R >>"
        )
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    parts = [b"%PDF-1.4\n"]
    offsets = []
    offset = len(parts[0])
    for i, obj in enumerate(objects, start=1):
        offsets.append(offset)
        chunk = f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
        parts.append(chunk)
        offset += len(chunk)
    n = len(objects) + 1
    xref = [f"xref\n0 {n}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    xref += [f"{off:010d} 00000 n \n".encode("latin-1") for off in offsets]
    trailer = f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{offset}\n%%EOF".encode("latin-1")
    return b"".join(parts) + b"".join(xref) + trailer
