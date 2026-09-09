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
