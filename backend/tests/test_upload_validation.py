"""Fichiers piégés : le type réel est lu dans les octets, jamais dans le nom ni le
Content-Type déclarés, et le fichier est stocké avec l'extension du type détecté."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from PIL import Image

from apps.billing.models import Invoice, Subscription
from apps.core import uploads
from apps.press_review.models import SourceDocument
from apps.press_review.serializers import SourceDocumentUploadSerializer
from tests.factories import PlanFactory, SubscriptionFactory
from tests.image_fixtures import make_image_bytes
from tests.pdf_fixtures import make_minimal_pdf_bytes

HTML = b"<!doctype html><html><body><script>fetch('/api/auth/token/refresh/',{method:'POST'})</script></body></html>"
SVG = (
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" onload="alert(document.domain)">'
    b"<script>alert(1)</script></svg>"
)


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _upload(client, name, content, content_type):
    return client.post(
        "/api/documents/", {"file": SimpleUploadedFile(name, content, content_type=content_type)}, format="multipart"
    )


def _heic_bytes():
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    buffer = io.BytesIO()
    try:
        Image.new("RGB", (64, 48), "white").save(buffer, format="HEIF", quality=50)
    except Exception as exc:  # noqa: BLE001 - encodeur HEIF absent de la roue installée
        pytest.skip(f"Encodage HEIF indisponible : {exc}")
    return buffer.getvalue()


# --------------------------------------------------------------------------- acceptés


@pytest.mark.django_db
def test_real_pdf_is_accepted_and_stored_as_pdf(authenticated_client, organization):
    response = _upload(authenticated_client, "Cameroon Tribune.pdf", make_minimal_pdf_bytes(["Texte."]), "application/pdf")

    assert response.status_code == 201, response.data
    document = SourceDocument.objects.get(pk=response.data["id"])
    assert document.kind == SourceDocument.Kind.PDF
    assert document.original_filename == "Cameroon Tribune.pdf"
    assert document.file.name.startswith(f"organizations/{organization.id}/source_documents/")
    assert document.file.name.endswith(".pdf")


@pytest.mark.parametrize(
    ("fmt", "extension"), [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")]
)
@pytest.mark.django_db
def test_photos_are_accepted_with_the_extension_of_their_real_format(authenticated_client, fmt, extension):
    # Nom et Content-Type mensongers : seul le contenu compte.
    response = _upload(authenticated_client, "coupure.pdf", make_image_bytes(fmt=fmt), "application/pdf")

    assert response.status_code == 201, response.data
    document = SourceDocument.objects.get(pk=response.data["id"])
    assert document.kind == SourceDocument.Kind.IMAGE
    assert document.file.name.endswith(extension)
    assert document.original_filename == "coupure.pdf"  # affiché tel que choisi par l'utilisateur


@pytest.mark.django_db
def test_iphone_heic_photo_is_accepted(authenticated_client):
    response = _upload(authenticated_client, "IMG_0001.HEIC", _heic_bytes(), "image/heic")

    assert response.status_code == 201, response.data
    document = SourceDocument.objects.get(pk=response.data["id"])
    assert document.kind == SourceDocument.Kind.IMAGE
    assert document.file.name.endswith(".heic")


@pytest.mark.django_db
def test_photo_named_html_is_stored_as_an_image_never_as_html(authenticated_client):
    response = _upload(authenticated_client, "photo.html", make_image_bytes(fmt="JPEG"), "text/html")

    assert response.status_code == 201, response.data
    document = SourceDocument.objects.get(pk=response.data["id"])
    assert document.file.name.endswith(".jpg")
    assert ".html" not in document.file.name


# --------------------------------------------------------------------------- refusés


@pytest.mark.parametrize(
    ("name", "content", "content_type"),
    [
        pytest.param("article.pdf", HTML, "application/pdf", id="html-deguise-en-pdf"),
        pytest.param("logo.svg", SVG, "image/svg+xml", id="svg"),
        pytest.param("photo.png", SVG, "image/png", id="svg-deguise-en-png"),
        pytest.param("article.pdf", b"%PDF-1.4\n" + HTML, "application/pdf", id="polyglotte-entete-pdf-puis-html"),
        pytest.param("photo.jpg", b"\xff\xd8\xff\xe0" + HTML, "image/jpeg", id="polyglotte-entete-jpeg-puis-html"),
        pytest.param("photo.png", b"\x89PNG\r\n\x1a\n" + HTML, "image/png", id="polyglotte-entete-png-puis-html"),
        pytest.param("article.pdf", make_minimal_pdf_bytes(["Texte."])[:150], "application/pdf", id="pdf-tronque"),
        pytest.param("anim.gif", make_image_bytes(fmt="GIF"), "image/gif", id="gif-non-accepte"),
        pytest.param("scan.tiff", make_image_bytes(fmt="TIFF"), "image/tiff", id="tiff-non-accepte"),
        pytest.param("notes.txt", b"bonjour", "text/plain", id="texte"),
        pytest.param("page.html", HTML, "text/html", id="html"),
    ],
)
@pytest.mark.django_db
def test_disguised_or_unsupported_files_are_rejected(authenticated_client, name, content, content_type):
    response = _upload(authenticated_client, name, content, content_type)

    assert response.status_code == 400
    assert "file" in response.data["errors"]
    assert not SourceDocument.objects.exists()


@pytest.mark.django_db
def test_unsupported_format_message_lists_accepted_formats(authenticated_client):
    response = _upload(authenticated_client, "logo.svg", SVG, "image/svg+xml")

    assert response.data["errors"]["file"] == ["Formats acceptés : PDF, ou photo (JPG, PNG, WebP, HEIC)."]


def test_size_limit_is_still_enforced():
    assert SourceDocumentUploadSerializer().fields["file"].max_size == 30 * 1024 * 1024
    big_png = make_image_bytes(size=(1200, 1200)) + b"\0" * (1024 * 1024)

    with pytest.raises(uploads.UploadRejected, match="taille maximale de 1 Mo"):
        uploads.validate_upload(
            SimpleUploadedFile("grande.png", big_png, content_type="image/png"),
            allowed_types=uploads.SOURCE_DOCUMENT_TYPES, max_size=1024 * 1024, formats_message="?",
        )


def test_validate_upload_rejects_an_empty_file():
    with pytest.raises(uploads.UploadRejected, match="vide"):
        uploads.validate_upload(
            SimpleUploadedFile("vide.pdf", b"", content_type="application/pdf"),
            allowed_types=uploads.SOURCE_DOCUMENT_TYPES, max_size=1024, formats_message="?",
        )


@pytest.mark.parametrize(
    ("content", "expected"),
    [(make_minimal_pdf_bytes(["Gros PDF."]), uploads.PDF), (make_image_bytes(fmt="JPEG"), uploads.JPEG)],
)
def test_large_uploads_written_to_disk_are_verified_too(content, expected):
    """Au-delà de 2,5 Mo, Django écrit le fichier sur disque (TemporaryUploadedFile)."""
    upload = TemporaryUploadedFile("scan.bin", "application/octet-stream", len(content), None)
    upload.write(content)
    upload.seek(0)
    try:
        detected = uploads.validate_upload(
            upload, allowed_types=uploads.SOURCE_DOCUMENT_TYPES, max_size=30 * 1024 * 1024, formats_message="?"
        )
        assert detected is expected
        assert upload.name == f"scan{expected.extension}"
        assert upload.read() == content  # rembobiné, prêt à être stocké
    finally:
        upload.close()


def test_detection_ignores_the_declared_name_and_type():
    png = SimpleUploadedFile("facture.pdf", make_image_bytes(), content_type="application/pdf")
    assert uploads.detect_file_type(png) is uploads.PNG
    assert uploads.detect_file_type(SimpleUploadedFile("x.png", SVG, content_type="image/png")) is None


def test_avif_is_not_mistaken_for_heif():
    avif_header = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf" + b"\0" * 32
    assert uploads.detect_file_type(SimpleUploadedFile("photo.heic", avif_header)) is None


# --------------------------------------------------------------------------- justificatif


@pytest.fixture
def pending_bank_invoice(organization, settings):
    # Dépôt de justificatif en libre-service : seulement hors mode manuel.
    settings.BILLING_MODE = "online"
    from django.utils import timezone

    subscription = SubscriptionFactory(
        organization=organization, plan=PlanFactory(code="pro"), provider=Subscription.Provider.BANK_TRANSFER
    )
    return Invoice.objects.create(
        organization=organization, subscription=subscription, provider=Subscription.Provider.BANK_TRANSFER,
        amount=0, period_start=timezone.now(), period_end=timezone.now(),
    )


def _post_proof(client, invoice, name, content, content_type):
    return client.post(
        f"/api/billing/invoices/{invoice.id}/proof/",
        {"proof": SimpleUploadedFile(name, content, content_type=content_type)},
        format="multipart",
    )


@pytest.mark.django_db
def test_payment_proof_must_really_be_a_pdf_jpg_or_png(authenticated_client, pending_bank_invoice):
    response = _post_proof(authenticated_client, pending_bank_invoice, "recu.pdf", HTML, "application/pdf")

    assert response.status_code == 400
    assert response.data["errors"]["proof"] == ["Justificatif accepté : PDF, JPG ou PNG."]
    pending_bank_invoice.refresh_from_db()
    assert not pending_bank_invoice.proof_file
    assert pending_bank_invoice.status == Invoice.Status.PENDING


@pytest.mark.django_db
def test_payment_proof_is_stored_with_its_detected_extension(authenticated_client, pending_bank_invoice):
    response = _post_proof(authenticated_client, pending_bank_invoice, "recu.html", make_image_bytes(fmt="JPEG"), "text/html")

    assert response.status_code == 200, response.data
    pending_bank_invoice.refresh_from_db()
    assert pending_bank_invoice.proof_file.name.endswith(".jpg")


@pytest.mark.django_db
def test_payment_proof_rejects_webp(authenticated_client, pending_bank_invoice):
    response = _post_proof(authenticated_client, pending_bank_invoice, "recu.webp", make_image_bytes(fmt="WEBP"), "image/webp")

    assert response.status_code == 400
