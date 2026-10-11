"""Fichiers clients privés : l'API ne renvoie que des liens signés, à durée de vie courte et
liés au fichier, servis avec des en-têtes qui neutralisent tout contenu actif."""
import re
import time
from urllib.parse import urlparse

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from apps.billing.models import Invoice, Subscription
from apps.core import media
from apps.press_review.models import GeneratedReview, PressReviewJob, SourceDocument
from tests.factories import PlanFactory, SubscriptionFactory
from tests.image_fixtures import make_image_bytes
from tests.pdf_fixtures import make_minimal_pdf_bytes

SIGNED_PATH = re.compile(r"^/api/media/(?P<expires>\d+)/(?P<signature>[\w-]+)/(?P<path>.+)$")


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _path_of(url):
    return urlparse(url).path


def _upload_photo(client):
    response = client.post(
        "/api/documents/",
        {"file": SimpleUploadedFile("coupure.png", make_image_bytes(), content_type="image/png")},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    return response.data


# --------------------------------------------------------------------------- URL signées


@pytest.mark.django_db
def test_document_url_is_signed_and_never_public(authenticated_client, organization):
    data = _upload_photo(authenticated_client)

    path = _path_of(data["file"])
    assert "/media/organizations/" not in path.replace("/api/media/", "/")
    match = SIGNED_PATH.match(path)
    assert match, path
    assert match["path"].startswith(f"organizations/{organization.id}/source_documents/")
    assert int(match["expires"]) > time.time()


@pytest.mark.django_db
def test_signed_url_serves_the_file_with_protective_headers(authenticated_client):
    data = _upload_photo(authenticated_client)

    response = Client().get(_path_of(data["file"]))  # sans jeton : la signature suffit

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == SourceDocument.objects.get(pk=data["id"]).file.read()
    assert response["Content-Type"] == "image/png"
    assert response["Content-Disposition"] == "inline"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response["Content-Security-Policy"]
    assert "default-src 'none'" in response["Content-Security-Policy"]
    assert response["Cache-Control"].startswith("private, max-age=")


@pytest.mark.django_db
def test_pdf_is_downloaded_not_rendered_inline(authenticated_client, organization):
    document = SourceDocument.objects.create(
        organization=organization,
        file=ContentFile(make_minimal_pdf_bytes(["<script>alert(1)</script>"]), name="a.pdf"),
        original_filename="a.pdf",
    )

    response = Client().get(document.file.url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == "attachment"


@pytest.mark.django_db
def test_legacy_file_with_dangerous_extension_is_served_as_inert_binary(organization):
    """Fichier déposé avant la validation stricte (ex. .html) : jamais interprété."""
    document = SourceDocument.objects.create(
        organization=organization, file=ContentFile(b"<script>alert(1)</script>", name="vieux.html"),
        original_filename="vieux.html",
    )

    response = Client().get(document.file.url)

    assert response["Content-Type"] == "application/octet-stream"
    assert response["Content-Disposition"] == "attachment"
    assert "sandbox" in response["Content-Security-Policy"]


@pytest.mark.django_db
def test_tampered_signature_is_refused(authenticated_client):
    match = SIGNED_PATH.match(_path_of(_upload_photo(authenticated_client)["file"]))
    forged = f"/api/media/{match['expires']}/{match['signature'][:-2]}xx/{match['path']}"

    assert Client().get(forged).status_code == 403


@pytest.mark.django_db
def test_signature_is_bound_to_the_file(authenticated_client):
    first = SIGNED_PATH.match(_path_of(_upload_photo(authenticated_client)["file"]))
    second = SIGNED_PATH.match(_path_of(_upload_photo(authenticated_client)["file"]))

    other_file = f"/api/media/{first['expires']}/{first['signature']}/{second['path']}"

    assert Client().get(other_file).status_code == 403


@pytest.mark.django_db
def test_extending_the_expiry_breaks_the_signature(authenticated_client):
    match = SIGNED_PATH.match(_path_of(_upload_photo(authenticated_client)["file"]))
    later = int(match["expires"]) + 86400

    assert Client().get(f"/api/media/{later}/{match['signature']}/{match['path']}").status_code == 403


@pytest.mark.django_db
def test_expired_link_is_refused(organization, settings):
    settings.MEDIA_URL_MAX_AGE = 1800
    document = SourceDocument.objects.create(
        organization=organization, file=ContentFile(make_image_bytes(), name="p.png"), original_filename="p.png"
    )
    an_hour_ago = time.time() - 3600
    url = media.signed_media_url(document.file.name, now=an_hour_ago)

    response = Client().get(url)

    assert response.status_code == 403
    assert "expiré" in response.content.decode()


def test_links_issued_in_the_same_window_are_identical_and_live_long_enough(settings):
    """Même URL d'un polling à l'autre (cache navigateur), validité entre 2/3 et 3/3 de la durée."""
    settings.MEDIA_URL_MAX_AGE = 1800
    start = 1_800_000_000  # multiple de la fenêtre (600 s)

    assert media.signed_media_url("a.png", now=start + 1) == media.signed_media_url("a.png", now=start + 599)
    for now in (start, start + 599):
        remaining = media._expiry(now) - now
        assert 1200 <= remaining <= 1800


def test_path_traversal_is_refused_even_with_a_valid_signature(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    (tmp_path / "secret.txt").write_text("hors du dossier media")

    response = Client().get(media.signed_media_url("../secret.txt"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_missing_file_returns_404():
    assert Client().get(media.signed_media_url("organizations/x/absent.png")).status_code == 404


@pytest.mark.django_db
def test_x_accel_redirect_hands_the_file_to_nginx(organization, settings):
    settings.MEDIA_X_ACCEL_REDIRECT = True
    document = SourceDocument.objects.create(
        organization=organization, file=ContentFile(make_image_bytes(), name="p.png"), original_filename="p.png"
    )

    response = Client().get(document.file.url)

    assert response.status_code == 200
    assert response["X-Accel-Redirect"] == f"/protected-media/{document.file.name}"
    assert response.content == b""
    assert response["X-Content-Type-Options"] == "nosniff"


def test_public_media_path_is_not_served():
    assert Client().get("/media/organizations/x/source_documents/a.png").status_code == 404


def test_only_safe_methods_are_allowed():
    assert Client().post(media.signed_media_url("a.png")).status_code == 405


# --------------------------------------------------------------------------- autres champs


@pytest.mark.django_db
def test_job_detail_documents_carry_signed_urls(authenticated_client, organization):
    job = PressReviewJob.objects.create(organization=organization, status=PressReviewJob.Status.REVIEW_READY)
    SourceDocument.objects.create(
        organization=organization, job=job, file=ContentFile(make_image_bytes(), name="p.png"), original_filename="p.png"
    )

    data = authenticated_client.get(f"/api/jobs/{job.id}/").data

    assert SIGNED_PATH.match(_path_of(data["documents"][0]["file"]))


@pytest.mark.django_db
def test_review_files_and_export_url_are_signed(authenticated_client, organization):
    job = PressReviewJob.objects.create(organization=organization, status=PressReviewJob.Status.REVIEW_READY)
    review = GeneratedReview.objects.create(job=job, summary_markdown="# Revue", generated_at=timezone.now())
    review.docx_file.save("revue.docx", ContentFile(b"PK\x03\x04docx"), save=True)

    review_data = authenticated_client.get(f"/api/jobs/{job.id}/review/").data
    export = authenticated_client.get(f"/api/jobs/{job.id}/review/export/", {"export_format": "docx"})

    assert SIGNED_PATH.match(_path_of(review_data["docx_file"]))
    assert export.status_code == 200
    assert SIGNED_PATH.match(_path_of(export.data["url"]))
    downloaded = Client().get(_path_of(export.data["url"]))
    assert downloaded["Content-Disposition"] == "attachment"
    assert downloaded["Content-Type"].startswith("application/vnd.openxmlformats")


@pytest.mark.django_db
def test_invoice_proof_url_is_signed(authenticated_client, organization):
    subscription = SubscriptionFactory(organization=organization, plan=PlanFactory())
    invoice = Invoice.objects.create(
        organization=organization, subscription=subscription, provider=Subscription.Provider.BANK_TRANSFER,
        amount=0, period_start=timezone.now(), period_end=timezone.now(),
    )
    invoice.proof_file.save("recu.pdf", ContentFile(make_minimal_pdf_bytes(["Reçu"])), save=True)

    # Le justificatif n'est plus exposé dans la liste des factures (mode manuel) : seul le
    # staff le consulte, et son URL reste signée comme tout fichier client.
    assert SIGNED_PATH.match(_path_of(invoice.proof_file.url))
