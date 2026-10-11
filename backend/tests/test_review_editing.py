"""Relire, corriger, diffuser : corrections de la revue (notices, ordre, rubriques, titre,
date), version IA conservée et restaurable, exports périmés à chaque correction, points
clés masqués ou reclassés, renommage et suppression d'une revue."""
from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
from apps.ai_pipeline.export import _build_pdf_html
from apps.ai_pipeline.press_format import build_structured, present, to_markdown
from apps.billing.services import SubscriptionService
from apps.press_review.models import GeneratedReview, Highlight, PipelineStepRun, PressReviewJob, SourceDocument
from tests.factories import (
    DetectionCategoryFactory,
    MembershipFactory,
    OrganizationFactory,
    SubscriptionFactory,
    UserFactory,
)


def _authenticate(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")


def _ai_structured():
    """Revue telle que l'IA la rédige : LE MESSAGER lu avant CAMEROON TRIBUNE, mais le
    classement affiche CAMEROON TRIBUNE en premier (journal le plus lu)."""
    return build_structured(
        entries=[
            {"source": "LE MESSAGER", "rubrique": "generale", "headline": "Le pays retient son souffle",
             "summary": "Le Messager revient sur la crise.", "documents": ["messager.jpg"]},
            {"source": "CAMEROON TRIBUNE", "rubrique": "generale", "headline": "Une volonté de transparence",
             "summary": "Le quotidien gouvernemental ouvre sur la réforme.", "documents": ["ct.jpg"]},
            {"source": "ECOMATIN", "rubrique": "economie", "headline": "Le cacao flambe",
             "summary": "Les cours du cacao atteignent un record.", "documents": ["eco.jpg"]},
        ],
        country="CAMEROUN",
        date_label="Jeudi 5 mars 2026",
    )


@pytest.fixture
def ready_job(db, organization, user):
    job = PressReviewJob.objects.create(
        organization=organization, created_by=user, title="Revue du jeudi", status=PressReviewJob.Status.REVIEW_READY
    )
    structured = _ai_structured()
    GeneratedReview.objects.create(
        job=job, structured=structured, summary_markdown=to_markdown(structured), generated_at=timezone.now()
    )
    return job


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _with_cached_exports(review):
    review.pdf_file.save(f"revue-{review.job_id}.pdf", ContentFile(b"%PDF-ancien"), save=False)
    review.docx_file.save(f"revue-{review.job_id}.docx", ContentFile(b"ancien docx"), save=False)
    review.save()
    return review.pdf_file.storage, review.pdf_file.name, review.docx_file.name


def _sections_payload(api_client, job):
    """Rubriques telles que l'éditeur les renvoie : la forme du GET."""
    review = api_client.get(f"/api/jobs/{job.id}/review/").data
    return [{"key": s["key"], "entries": s["entries"]} for s in review["structured"]["sections"]]


# --------------------------------------------------------------------------- lecture


@pytest.mark.django_db
def test_review_exposes_edit_state_and_the_rubric_catalog(authenticated_client, ready_job):
    response = authenticated_client.get(f"/api/jobs/{ready_job.id}/review/")

    assert response.status_code == 200
    assert response.data["is_edited"] is False
    assert response.data["edited_at"] is None
    assert response.data["edited_by_name"] is None
    assert [r["key"] for r in response.data["rubriques"]][:2] == ["generale", "economie"]
    assert {"key", "title", "color", "icon"} == set(response.data["rubriques"][0])


# --------------------------------------------------------------------------- corrections


@pytest.mark.django_db
def test_editing_notices_keeps_the_chosen_order_and_the_ai_original(authenticated_client, ready_job, user):
    sections = _sections_payload(authenticated_client, ready_job)
    generale, economie = sections
    assert [e["source"] for e in generale["entries"]] == ["CAMEROON TRIBUNE", "LE MESSAGER"]  # classement IA

    # Corriger une notice et un nom de journal, remonter LE MESSAGER, déplacer ECOMATIN en
    # presse générale.
    generale["entries"][1]["headline"] = "« Le pays retient son souffle ! »"
    generale["entries"][1]["summary"] = "  Résumé   corrigé\npar la cellule.  "
    generale["entries"][0]["source"] = "nouvelle gazette"
    generale["entries"].reverse()
    generale["entries"].append(economie["entries"][0])
    payload = {"sections": [generale]}

    response = authenticated_client.patch(f"/api/jobs/{ready_job.id}/review/", payload, format="json")

    assert response.status_code == 200, response.data
    shown = response.data["structured"]["sections"]
    assert [s["key"] for s in shown] == ["generale"]  # rubrique vidée = retirée
    # Ordre choisi gardé (NOUVELLE GAZETTE, inconnue, serait sinon classée après ECOMATIN).
    assert [e["source"] for e in shown[0]["entries"]] == ["LE MESSAGER", "NOUVELLE GAZETTE", "ECOMATIN"]
    first = shown[0]["entries"][0]
    assert first["headline"] == "Le pays retient son souffle !"  # guillemets ajoutés au rendu
    assert first["summary"] == "Résumé corrigé par la cellule."
    assert response.data["is_edited"] is True
    assert response.data["edited_by_name"] == user.full_name

    review = GeneratedReview.objects.get(job=ready_job)
    assert review.original_structured == _ai_structured()
    assert review.edited_by == user and review.edited_at is not None
    assert "Résumé corrigé par la cellule." in review.summary_markdown
    assert "Le cacao flambe" in review.summary_markdown  # toujours là, dans sa nouvelle rubrique
    assert review.summary_markdown.index("LE MESSAGER") < review.summary_markdown.index("NOUVELLE GAZETTE")
    assert "CAMEROON TRIBUNE" not in review.summary_markdown


@pytest.mark.django_db
def test_deleted_notice_disappears_from_the_review_and_the_pdf(authenticated_client, ready_job):
    sections = _sections_payload(authenticated_client, ready_job)
    sections[0]["entries"] = [e for e in sections[0]["entries"] if e["source"] != "LE MESSAGER"]

    response = authenticated_client.patch(f"/api/jobs/{ready_job.id}/review/", {"sections": sections}, format="json")

    assert response.status_code == 200, response.data
    review = GeneratedReview.objects.get(job=ready_job)
    html = _build_pdf_html(review)
    assert "LE MESSAGER" not in html and "Le pays retient son souffle" not in html
    assert "CAMEROON TRIBUNE" in html and "ECOMATIN" in html


@pytest.mark.django_db
def test_every_edit_clears_the_cached_exports(
    authenticated_client, ready_job, media_root, django_capture_on_commit_callbacks
):
    review = GeneratedReview.objects.get(job=ready_job)
    storage, pdf_name, docx_name = _with_cached_exports(review)

    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client.patch(
            f"/api/jobs/{ready_job.id}/review/", {"date_label": "Vendredi 6 mars 2026"}, format="json"
        )

    assert response.status_code == 200, response.data
    assert response.data["pdf_file"] is None and response.data["docx_file"] is None
    assert not storage.exists(pdf_name) and not storage.exists(docx_name)
    review.refresh_from_db()
    assert review.structured["date_label"] == "Vendredi 6 mars 2026"
    assert "Vendredi 6 mars 2026" in _build_pdf_html(review)


@pytest.mark.django_db
def test_title_and_date_can_be_edited_without_freezing_the_newspaper_ranking(authenticated_client, ready_job):
    response = authenticated_client.patch(
        f"/api/jobs/{ready_job.id}/review/",
        {"title": "  Revue spéciale réforme  ", "date_label": "Jeudi 5 mars 2026 (édition du soir)"},
        format="json",
    )

    assert response.status_code == 200, response.data
    ready_job.refresh_from_db()
    assert ready_job.title == "Revue spéciale réforme"
    review = GeneratedReview.objects.get(job=ready_job)
    assert "manual_order" not in review.structured
    assert response.data["structured"]["date_label"] == "Jeudi 5 mars 2026 (édition du soir)"
    assert "Revue spéciale réforme" in _build_pdf_html(review)


@pytest.mark.django_db
def test_a_second_edit_keeps_the_first_ai_version(authenticated_client, ready_job):
    url = f"/api/jobs/{ready_job.id}/review/"
    authenticated_client.patch(url, {"date_label": "Première correction"}, format="json")
    authenticated_client.patch(url, {"date_label": "Seconde correction"}, format="json")

    review = GeneratedReview.objects.get(job=ready_job)
    assert review.structured["date_label"] == "Seconde correction"
    assert review.original_structured["date_label"] == "Jeudi 5 mars 2026"


@pytest.mark.django_db
def test_restore_brings_back_the_ai_version(authenticated_client, ready_job, media_root):
    url = f"/api/jobs/{ready_job.id}/review/"
    sections = _sections_payload(authenticated_client, ready_job)
    sections[0]["entries"][0]["summary"] = "Texte retouché"
    authenticated_client.patch(url, {"sections": sections}, format="json")
    _with_cached_exports(GeneratedReview.objects.get(job=ready_job))

    response = authenticated_client.post(f"{url}restore/")

    assert response.status_code == 200, response.data
    assert response.data["is_edited"] is False
    assert response.data["pdf_file"] is None
    review = GeneratedReview.objects.get(job=ready_job)
    assert review.structured == _ai_structured()
    assert review.original_structured == {} and review.edited_by is None
    assert "Texte retouché" not in review.summary_markdown
    # Classement automatique rétabli.
    assert [e["source"] for e in present(review.structured)["sections"][0]["entries"]][0] == "CAMEROON TRIBUNE"

    again = authenticated_client.post(f"{url}restore/")
    assert again.status_code == 400
    assert "rien à restaurer" in again.data["detail"]


@pytest.mark.parametrize(
    ("sections", "message"),
    [
        ("pas une liste", "rubriques de la revue sont invalides"),
        ([{"key": "faits-divers", "entries": []}], "Rubrique inconnue"),
        ([{"key": "generale", "entries": []}, {"key": "generale", "entries": []}], "apparaît deux fois"),
        ([{"key": "generale", "entries": []}], "au moins une notice"),
        (
            [{"key": "generale", "entries": [{"source": "  ", "headline": "Titre", "summary": "Résumé"}]}],
            "LA PRESSE GÉNÉRALE, notice 1 : le nom du journal est obligatoire",
        ),
        (
            [{"key": "economie", "entries": [{"source": "ECOMATIN", "headline": "", "summary": "Ok"},
                                             {"source": "LE JOUR", "headline": " ", "summary": ""}]}],
            "notice 2 (LE JOUR) : indiquez le titre de la une ou un résumé",
        ),
        (
            [{"key": "generale", "entries": [{"source": "LE JOUR", "headline": "", "summary": "x" * 5001}]}],
            "le résumé ne doit pas dépasser 5000 caractères",
        ),
        (
            [{"key": "generale", "entries": [{"source": 12, "headline": "", "summary": "Résumé"}]}],
            "le nom du journal doit être du texte",
        ),
    ],
)
@pytest.mark.django_db
def test_invalid_edits_are_refused_with_a_clear_message(authenticated_client, ready_job, sections, message):
    response = authenticated_client.patch(f"/api/jobs/{ready_job.id}/review/", {"sections": sections}, format="json")

    assert response.status_code == 400
    assert message in response.data["detail"]
    assert GeneratedReview.objects.get(job=ready_job).original_structured == {}  # rien n'a été écrit


@pytest.mark.django_db
def test_an_empty_patch_or_a_blank_title_is_refused(authenticated_client, ready_job):
    url = f"/api/jobs/{ready_job.id}/review/"

    empty = authenticated_client.patch(url, {}, format="json")
    blank = authenticated_client.patch(url, {"title": "   "}, format="json")

    assert empty.status_code == 400 and "Aucune modification" in str(empty.data)
    assert blank.status_code == 400 and "Le titre de la revue ne peut pas être vide." in str(blank.data)


@pytest.mark.django_db
def test_a_concurrent_edit_is_detected_instead_of_overwritten(authenticated_client, ready_job):
    url = f"/api/jobs/{ready_job.id}/review/"
    first = authenticated_client.patch(url, {"date_label": "A", "expected_edited_at": None}, format="json")
    assert first.status_code == 200, first.data

    stale = authenticated_client.patch(url, {"date_label": "B", "expected_edited_at": None}, format="json")
    fresh = authenticated_client.patch(
        url, {"date_label": "C", "expected_edited_at": first.data["edited_at"]}, format="json"
    )

    assert stale.status_code == 409
    assert "modifiée entre-temps" in stale.data["detail"]
    assert fresh.status_code == 200, fresh.data
    assert GeneratedReview.objects.get(job=ready_job).structured["date_label"] == "C"


@pytest.mark.django_db
def test_a_review_still_being_drafted_cannot_be_edited(authenticated_client, ready_job):
    PressReviewJob.objects.filter(pk=ready_job.pk).update(status=PressReviewJob.Status.REVIEW_DRAFTING)

    response = authenticated_client.patch(f"/api/jobs/{ready_job.id}/review/", {"date_label": "X"}, format="json")

    assert response.status_code == 400
    assert "une fois prête" in response.data["detail"]


@pytest.mark.django_db
def test_a_legacy_markdown_review_can_only_be_renamed(authenticated_client, organization, user):
    job = PressReviewJob.objects.create(
        organization=organization, created_by=user, status=PressReviewJob.Status.REVIEW_READY, title="Ancienne"
    )
    GeneratedReview.objects.create(job=job, summary_markdown="# Synthèse libre")
    url = f"/api/jobs/{job.id}/review/"

    refused = authenticated_client.patch(url, {"sections": [{"key": "generale", "entries": []}]}, format="json")
    renamed = authenticated_client.patch(url, {"title": "Ancienne revue renommée"}, format="json")

    assert refused.status_code == 400 and "seul son titre" in refused.data["detail"]
    assert renamed.status_code == 200, renamed.data
    job.refresh_from_db()
    assert job.title == "Ancienne revue renommée"


@pytest.mark.django_db
def test_only_members_of_the_organization_can_edit(api_client, ready_job):
    outsider = UserFactory()
    MembershipFactory(organization=OrganizationFactory(), user=outsider)
    url = f"/api/jobs/{ready_job.id}/review/"

    anonymous = api_client.patch(url, {"date_label": "X"}, format="json")
    _authenticate(api_client, outsider)
    foreign = api_client.patch(url, {"date_label": "X"}, format="json")
    foreign_restore = api_client.post(f"{url}restore/")

    assert anonymous.status_code == 401
    assert foreign.status_code == 404 and foreign_restore.status_code == 404
    assert GeneratedReview.objects.get(job=ready_job).structured == _ai_structured()


@pytest.mark.django_db
def test_a_simple_member_can_edit_the_review(api_client, ready_job):
    member = UserFactory(full_name="")
    MembershipFactory(organization=ready_job.organization, user=member, role=Membership.Role.MEMBER)
    _authenticate(api_client, member)

    response = api_client.patch(f"/api/jobs/{ready_job.id}/review/", {"date_label": "X"}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["edited_by_name"] == member.email


def test_the_newspaper_ranking_only_applies_to_reviews_not_reordered_by_hand():
    structured = _ai_structured()
    assert [e["source"] for e in present(structured)["sections"][0]["entries"]] == ["CAMEROON TRIBUNE", "LE MESSAGER"]

    structured["manual_order"] = True
    assert [e["source"] for e in present(structured)["sections"][0]["entries"]] == ["LE MESSAGER", "CAMEROON TRIBUNE"]


# --------------------------------------------------------------------------- points clés


@pytest.fixture
def highlights(ready_job):
    legal = DetectionCategoryFactory(name="Risque juridique", sort_order=1)
    important = DetectionCategoryFactory(name="Point important", sort_order=2)
    kept = Highlight.objects.create(
        job=ready_job, category=legal, excerpt="Le directeur est accusé sans preuve", order=0
    )
    false_positive = Highlight.objects.create(
        job=ready_job, category=important, excerpt="Un faux positif repéré par erreur", order=1
    )
    return kept, false_positive, legal, important


@pytest.mark.django_db
def test_a_hidden_key_point_leaves_the_exports_and_the_counters(
    authenticated_client, ready_job, highlights, media_root, django_capture_on_commit_callbacks
):
    _kept, false_positive, _legal, _important = highlights
    review = GeneratedReview.objects.get(job=ready_job)
    storage, pdf_name, _docx_name = _with_cached_exports(review)
    url = f"/api/jobs/{ready_job.id}/highlights/{false_positive.id}/"

    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client.patch(url, {"hidden": True}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["hidden"] is True
    review.refresh_from_db()
    assert not review.pdf_file and not storage.exists(pdf_name)
    html = _build_pdf_html(review)
    assert "Le directeur est accusé sans preuve" in html
    assert "Un faux positif repéré par erreur" not in html and "Point important" not in html

    # Toujours listé (pour pouvoir le réafficher), filtrable, et absent des compteurs.
    listed = authenticated_client.get(f"/api/jobs/{ready_job.id}/highlights/").data
    assert {h["excerpt"]: h["hidden"] for h in listed}["Un faux positif repéré par erreur"] is True
    visible = authenticated_client.get(f"/api/jobs/{ready_job.id}/highlights/?hidden=false").data
    assert [h["excerpt"] for h in visible] == ["Le directeur est accusé sans preuve"]
    jobs = authenticated_client.get("/api/jobs/").data["results"]
    assert jobs[0]["highlights_count"] == 1
    assert authenticated_client.get("/api/jobs/stats/").data["highlights"] == 1

    shown_again = authenticated_client.patch(url, {"hidden": False}, format="json")
    assert shown_again.status_code == 200 and shown_again.data["hidden"] is False
    assert "Un faux positif repéré par erreur" in _build_pdf_html(GeneratedReview.objects.get(job=ready_job))


@pytest.mark.django_db
def test_a_key_point_can_move_to_another_active_category(authenticated_client, ready_job, organization, highlights):
    kept, _false_positive, _legal, important = highlights
    url = f"/api/jobs/{ready_job.id}/highlights/{kept.id}/"
    own_category = DetectionCategoryFactory(organization=organization, name="Image du ministère")
    foreign_category = DetectionCategoryFactory(organization=OrganizationFactory(), name="Autre client")
    inactive = DetectionCategoryFactory(is_active=False)

    moved = authenticated_client.patch(url, {"category": str(important.id)}, format="json")
    assert moved.status_code == 200, moved.data
    assert moved.data["category"]["name"] == "Point important"
    assert authenticated_client.patch(url, {"category": str(own_category.id)}, format="json").status_code == 200

    foreign = authenticated_client.patch(url, {"category": str(foreign_category.id)}, format="json")
    disabled = authenticated_client.patch(url, {"category": str(inactive.id)}, format="json")
    malformed = authenticated_client.patch(url, {"category": "pas-un-uuid"}, format="json")
    empty = authenticated_client.patch(url, {}, format="json")

    assert foreign.status_code == 400 and "introuvable" in str(foreign.data)
    assert disabled.status_code == 400 and "désactivée" in str(disabled.data)
    assert malformed.status_code == 400 and "Catégorie invalide" in str(malformed.data)
    assert empty.status_code == 400
    kept.refresh_from_db()
    assert kept.category == own_category


@pytest.mark.django_db
def test_key_points_of_another_job_or_organization_are_out_of_reach(
    api_client, authenticated_client, ready_job, highlights
):
    kept = highlights[0]
    other_job = PressReviewJob.objects.create(organization=ready_job.organization, status="REVIEW_READY")

    wrong_job = authenticated_client.patch(
        f"/api/jobs/{other_job.id}/highlights/{kept.id}/", {"hidden": True}, format="json"
    )
    outsider = UserFactory()
    MembershipFactory(organization=OrganizationFactory(), user=outsider)
    _authenticate(api_client, outsider)
    foreign = api_client.patch(f"/api/jobs/{ready_job.id}/highlights/{kept.id}/", {"hidden": True}, format="json")

    assert wrong_job.status_code == 404 and foreign.status_code == 404
    kept.refresh_from_db()
    assert kept.hidden is False


# --------------------------------------------------------------------------- renommer / supprimer


@pytest.mark.django_db
def test_renaming_a_review_updates_the_title_and_clears_the_exports(authenticated_client, ready_job, media_root):
    _with_cached_exports(GeneratedReview.objects.get(job=ready_job))

    response = authenticated_client.patch(f"/api/jobs/{ready_job.id}/", {"title": "Revue du conseil"}, format="json")
    blank = authenticated_client.patch(f"/api/jobs/{ready_job.id}/", {"title": ""}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["title"] == "Revue du conseil"
    assert not GeneratedReview.objects.get(job=ready_job).pdf_file
    assert blank.status_code == 400 and "ne peut pas être vide" in str(blank.data)


def _job_with_content(organization, user, status=PressReviewJob.Status.REVIEW_READY):
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="À supprimer", status=status)
    document = SourceDocument.objects.create(
        organization=organization, job=job, uploaded_by=user, original_filename="une.jpg", kind="image",
        file=ContentFile(b"image", name="une.jpg"),
    )
    review = GeneratedReview.objects.create(job=job, structured=_ai_structured(), summary_markdown="x")
    review.pdf_file.save("revue.pdf", ContentFile(b"%PDF"), save=True)
    Highlight.objects.create(job=job, source_document=document, category=DetectionCategoryFactory(), excerpt="Extrait")
    PipelineStepRun.objects.create(job=job, step_name=PipelineStepRun.StepName.TEXT_EXTRACTION)
    return job, document, review


@pytest.mark.django_db
def test_the_author_can_delete_a_finished_review_and_its_files(
    api_client, organization, media_root, django_capture_on_commit_callbacks
):
    author = UserFactory()
    MembershipFactory(organization=organization, user=author, role=Membership.Role.MEMBER)
    SubscriptionFactory(organization=organization, current_period_start=timezone.now() - timedelta(days=1))
    job, document, review = _job_with_content(organization, author)
    storage = document.file.storage
    files = [document.file.name, review.pdf_file.name]
    assert all(storage.exists(name) for name in files)
    used_before = SubscriptionService.reviews_used(organization.subscription)
    _authenticate(api_client, author)

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.delete(f"/api/jobs/{job.id}/")

    assert response.status_code == 204
    assert not any(storage.exists(name) for name in files)
    assert not SourceDocument.objects.filter(job=job).exists()
    assert not GeneratedReview.objects.filter(job=job).exists()
    assert not Highlight.objects.filter(job=job).exists()
    assert not PipelineStepRun.objects.filter(job=job).exists()
    job.refresh_from_db()
    assert job.deleted_at is not None and job.title == ""
    # Invisible partout…
    assert api_client.get(f"/api/jobs/{job.id}/").status_code == 404
    assert api_client.get(f"/api/jobs/{job.id}/review/").status_code == 404
    assert api_client.get("/api/jobs/").data["count"] == 0
    assert api_client.get("/api/jobs/stats/").data["total"] == 0
    # … mais toujours décomptée du quota : supprimer puis relancer ne rend pas de revue.
    assert SubscriptionService.reviews_used(organization.subscription) == used_before == 1


@pytest.mark.django_db
def test_another_member_cannot_delete_but_an_admin_can(api_client, organization, user, media_root):
    job, _document, _review = _job_with_content(organization, user)
    colleague = UserFactory()
    MembershipFactory(organization=organization, user=colleague, role=Membership.Role.MEMBER)
    admin = UserFactory()
    MembershipFactory(organization=organization, user=admin, role=Membership.Role.ADMIN)

    _authenticate(api_client, colleague)
    refused = api_client.delete(f"/api/jobs/{job.id}/")
    _authenticate(api_client, admin)
    accepted = api_client.delete(f"/api/jobs/{job.id}/")

    assert refused.status_code == 403
    assert "auteur de la revue" in refused.data["detail"]
    assert accepted.status_code == 204


@pytest.mark.django_db
def test_a_failed_review_can_be_deleted_but_not_one_being_analysed(
    authenticated_client, organization, user, media_root
):
    failed, _d, _r = _job_with_content(organization, user, status=PressReviewJob.Status.FAILED)
    running, _d2, _r2 = _job_with_content(organization, user, status=PressReviewJob.Status.HIGHLIGHT_DETECTION)

    assert authenticated_client.delete(f"/api/jobs/{failed.id}/").status_code == 204
    response = authenticated_client.delete(f"/api/jobs/{running.id}/")

    assert response.status_code == 400
    assert "en cours d'analyse" in response.data["detail"]
    assert SourceDocument.objects.filter(job=running).exists()
    # Une revue supprimée ne peut plus être relancée.
    assert authenticated_client.post(f"/api/jobs/{failed.id}/retry/").status_code == 404


@pytest.mark.django_db
def test_a_review_of_another_organization_cannot_be_deleted(api_client, organization, user, media_root):
    job, _document, _review = _job_with_content(organization, user)
    outsider = UserFactory()
    MembershipFactory(organization=OrganizationFactory(), user=outsider, role=Membership.Role.OWNER)
    _authenticate(api_client, outsider)

    assert api_client.delete(f"/api/jobs/{job.id}/").status_code == 404
    assert api_client.patch(f"/api/jobs/{job.id}/", {"title": "Piraté"}, format="json").status_code == 404
    job.refresh_from_db()
    assert job.deleted_at is None and job.title == "À supprimer"


@pytest.mark.django_db
def test_deleting_a_review_from_the_admin_also_removes_its_files(
    organization, user, media_root, django_capture_on_commit_callbacks
):
    job, document, review = _job_with_content(organization, user)
    storage = document.file.storage
    names = [document.file.name, review.pdf_file.name]

    with django_capture_on_commit_callbacks(execute=True):
        job.delete()

    assert not any(storage.exists(name) for name in names)


@pytest.mark.django_db
def test_job_payloads_expose_the_author_for_the_delete_menu(authenticated_client, ready_job, user):
    listed = authenticated_client.get("/api/jobs/").data["results"][0]
    detail = authenticated_client.get(f"/api/jobs/{ready_job.id}/").data

    assert listed["created_by"] == user.id
    assert detail["created_by"] == user.id
