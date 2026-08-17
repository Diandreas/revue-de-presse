"""Rendu de la revue générée (Markdown) en PDF (WeasyPrint) et DOCX (python-docx).
Le rendu est mis en cache sur le modèle : un même format n'est généré qu'une fois."""
import io
import logging

import markdown as md
from django.core.files.base import ContentFile
from docx import Document

logger = logging.getLogger(__name__)

PDF_STYLE = """
<style>
  body { font-family: 'Helvetica Neue', Arial, sans-serif; color: #111827; line-height: 1.5; }
  h1 { color: #111827; border-bottom: 2px solid #2563EB; padding-bottom: 8px; }
  h2 { color: #1F2937; margin-top: 28px; }
  ul { margin-left: 0; padding-left: 20px; }
  li { margin-bottom: 6px; }
</style>
"""


def get_or_render_export(review, *, fmt):
    if fmt == "pdf":
        if not review.pdf_file:
            _render_pdf(review)
        return review.pdf_file
    if fmt == "docx":
        if not review.docx_file:
            _render_docx(review)
        return review.docx_file
    raise ValueError(f"Format d'export non supporté : {fmt}")


def _render_pdf(review):
    # Import paresseux : WeasyPrint a besoin de libs système natives (Pango/cairo,
    # présentes dans le Dockerfile) absentes de certains postes de dev (Windows sans
    # GTK). Un import en haut de fichier casserait aussi l'export DOCX, qui n'en a pas
    # besoin, dès que ces libs manquent.
    from weasyprint import HTML

    html_body = md.markdown(review.summary_markdown or "", extensions=["extra", "sane_lists"])
    html = f"<html><head>{PDF_STYLE}</head><body>{html_body}</body></html>"
    pdf_bytes = HTML(string=html).write_pdf()
    review.pdf_file.save(f"revue-{review.job_id}.pdf", ContentFile(pdf_bytes), save=False)
    review.save(update_fields=["pdf_file", "updated_at"])


def _render_docx(review):
    document = Document()
    for line in (review.summary_markdown or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            document.add_heading(stripped[4:], level=3)
        elif stripped.startswith("## "):
            document.add_heading(stripped[3:], level=2)
        elif stripped.startswith("# "):
            document.add_heading(stripped[2:], level=1)
        elif stripped.startswith(("- ", "* ")):
            document.add_paragraph(stripped[2:], style="List Bullet")
        else:
            document.add_paragraph(stripped)

    buffer = io.BytesIO()
    document.save(buffer)
    review.docx_file.save(f"revue-{review.job_id}.docx", ContentFile(buffer.getvalue()), save=False)
    review.save(update_fields=["docx_file", "updated_at"])
