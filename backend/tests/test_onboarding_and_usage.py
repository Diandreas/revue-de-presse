"""Parcours d'une entreprise qui vient de s'inscrire : essai gratuit, quotas lisibles,
gestion des documents en attente, invitations partageables."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Invitation, Membership
from apps.billing.models import Subscription
from apps.billing.services import (
    NO_SUBSCRIPTION_MESSAGE,
    TRIAL_EXPIRED_MESSAGE,
    SubscriptionService,
)
from apps.press_review.models import Highlight, PressReviewJob, SourceDocument
from apps.press_review.services.jobs import default_job_title
from tests.factories import (
    DetectionCategoryFactory,
    MembershipFactory,
    OrganizationFactory,
    PlanFactory,
    SubscriptionFactory,
    UserFactory,
)
from tests.pdf_fixtures import make_minimal_pdf_bytes


def _authenticate(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")


def _pdf(name="article.pdf"):
    return SimpleUploadedFile(
        name, make_minimal_pdf_bytes(["Le conseil municipal adopte un nouveau budget."]), content_type="application/pdf"
    )


@pytest.fixture
def starter_plan(db):
    return PlanFactory(code="starter", name="Starter", price_amount=50000, max_reviews_per_month=10)


# --- Essai gratuit -----------------------------------------------------------------


@pytest.mark.django_db
def test_registration_starts_a_free_trial_so_a_new_company_can_create_a_review(api_client, starter_plan, settings):
    """Régression : un compte tout juste créé recevait 403 « aucun abonnement actif » au
    lancement de sa toute première revue (paiements en mode simulé = aucun moyen d'activer).
    L'essai dure 7 jours par défaut (TRIAL_DAYS)."""
    response = api_client.post(
        "/api/auth/register/",
        {
            "email": "nouvelle@entreprise.cm",
            "password": "un-mot-de-passe-solide",
            "full_name": "Awa Nkoulou",
            "organization_name": "Presse Plus SARL",
            "phone_number": "+237 6 77 00 00 02",
            "accept_terms": True,
        },
    )
    assert response.status_code == 201, response.data

    subscription = Subscription.objects.get(organization__name="Presse Plus SARL")
    assert subscription.status == Subscription.Status.TRIALING
    assert subscription.plan == starter_plan
    assert subscription.current_period_end - subscription.current_period_start == timedelta(days=7)

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    upload = api_client.post("/api/documents/", {"file": _pdf()}, format="multipart")
    assert upload.status_code == 201, upload.data

    job = api_client.post("/api/jobs/", {"document_ids": [upload.data["id"]]}, format="json")
    assert job.status_code == 201, job.data


@pytest.mark.django_db
def test_trial_can_be_disabled(starter_plan, settings):
    settings.TRIAL_DAYS = 0
    org = OrganizationFactory()
    assert SubscriptionService.start_trial(organization=org) is None
    assert not Subscription.objects.filter(organization=org).exists()


@pytest.mark.django_db
def test_trial_falls_back_to_cheapest_plan_and_never_overwrites_an_existing_subscription(settings):
    settings.TRIAL_PLAN_CODE = "inexistant"
    cheapest = PlanFactory(code="mini", price_amount=1000)
    PlanFactory(code="maxi", price_amount=900000)
    org = OrganizationFactory()

    subscription = SubscriptionService.start_trial(organization=org)
    assert subscription.plan == cheapest

    assert SubscriptionService.start_trial(organization=org) is None  # déjà abonné : on ne touche à rien
    assert Subscription.objects.filter(organization=org).count() == 1


@pytest.mark.django_db
def test_expired_trial_denies_new_reviews_with_a_clear_message():
    org = OrganizationFactory()
    SubscriptionFactory(
        organization=org,
        status=Subscription.Status.TRIALING,
        current_period_start=timezone.now() - timedelta(days=20),
        current_period_end=timezone.now() - timedelta(days=6),
    )
    assert SubscriptionService.review_quota_denial(organization=org) == TRIAL_EXPIRED_MESSAGE
    assert SubscriptionService.has_quota_for_new_review(organization=org) is False


@pytest.mark.django_db
def test_quota_denial_message_is_returned_by_the_api(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role=Membership.Role.OWNER)
    document = SourceDocument.objects.create(organization=org, file=_pdf(), original_filename="a.pdf")

    _authenticate(api_client, user)
    response = api_client.post("/api/jobs/", {"document_ids": [str(document.id)]}, format="json")

    assert response.status_code == 403
    assert response.data["detail"] == NO_SUBSCRIPTION_MESSAGE


@pytest.mark.django_db
def test_start_trials_command_only_targets_organizations_without_subscription(starter_plan):
    without = OrganizationFactory(name="Sans abonnement")
    already = OrganizationFactory(name="Déjà client")
    paid = SubscriptionFactory(organization=already, status=Subscription.Status.ACTIVE)

    call_command("start_trials")

    assert Subscription.objects.get(organization=without).status == Subscription.Status.TRIALING
    paid.refresh_from_db()
    assert paid.status == Subscription.Status.ACTIVE


@pytest.mark.django_db
def test_subscription_api_exposes_usage(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role=Membership.Role.OWNER)
    plan = PlanFactory(max_reviews_per_month=10)
    SubscriptionFactory(
        organization=org,
        plan=plan,
        status=Subscription.Status.TRIALING,
        current_period_start=timezone.now() - timedelta(days=1),
        current_period_end=timezone.now() + timedelta(days=13),
    )
    PressReviewJob.objects.create(organization=org, title="Revue 1")
    PressReviewJob.objects.create(organization=org, title="Revue 2")

    _authenticate(api_client, user)
    data = api_client.get("/api/billing/subscription/").data

    assert data["is_trial"] is True
    assert data["reviews_used"] == 2
    assert data["reviews_limit"] == 10


# --- Revues et documents -------------------------------------------------------------


@pytest.mark.django_db
def test_job_list_includes_document_and_highlight_counts(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user)
    job = PressReviewJob.objects.create(organization=org, title="Revue")
    for name in ("a.pdf", "b.pdf"):
        SourceDocument.objects.create(organization=org, job=job, file=_pdf(name), original_filename=name)
    category = DetectionCategoryFactory()
    Highlight.objects.create(job=job, category=category, excerpt="Extrait 1")

    _authenticate(api_client, user)
    item = api_client.get("/api/jobs/").data["results"][0]

    assert item["documents_count"] == 2
    assert item["highlights_count"] == 1


@pytest.mark.django_db
def test_job_stats_cover_every_review_of_the_organization_only(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user)
    category = DetectionCategoryFactory()
    statuses = ["TEXT_EXTRACTION", "REVIEW_READY", "EXPORTED", "FAILED"] + ["REVIEW_READY"] * 22
    for status in statuses:  # > 1 page de liste : les stats ne doivent pas dépendre de la pagination
        job = PressReviewJob.objects.create(organization=org, title="R", status=status)
        Highlight.objects.create(job=job, category=category, excerpt="x")
    SourceDocument.objects.create(organization=org, job=job, file=_pdf(), original_filename="a.pdf")
    other = PressReviewJob.objects.create(organization=OrganizationFactory(), title="Ailleurs")
    Highlight.objects.create(job=other, category=category, excerpt="y")

    _authenticate(api_client, user)
    stats = api_client.get("/api/jobs/stats/").data

    assert stats == {"total": 26, "active": 1, "ready": 24, "failed": 1, "highlights": 26, "documents": 1}


@pytest.mark.django_db
def test_job_without_title_gets_a_dated_default_title(api_client, starter_plan):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role=Membership.Role.OWNER)
    SubscriptionService.start_trial(organization=org)
    document = SourceDocument.objects.create(organization=org, file=_pdf(), original_filename="a.pdf")

    _authenticate(api_client, user)
    response = api_client.post("/api/jobs/", {"title": "   ", "document_ids": [str(document.id)]}, format="json")

    assert response.status_code == 201, response.data
    assert response.data["title"] == default_job_title()
    assert response.data["title"].startswith("Revue de presse du ")


def test_default_job_title_is_in_french_whatever_the_server_locale():
    moment = timezone.make_aware(timezone.datetime(2026, 8, 3, 12, 0))
    assert default_job_title(moment) == "Revue de presse du 3 août 2026"


@pytest.mark.django_db
def test_reading_order_follows_the_users_selection_not_the_upload_completion_order(api_client, starter_plan):
    """Les photos sont envoyées en parallèle : elles n'arrivent pas sur le serveur dans
    l'ordre où l'utilisateur les a ajoutées. L'ordre de lecture de la revue doit être celui
    de `document_ids`, pas celui de création des fichiers."""
    from apps.ai_pipeline.tasks import _ordered_documents

    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role=Membership.Role.OWNER)
    SubscriptionService.start_trial(organization=org)
    first_uploaded, second_uploaded, third_uploaded = (
        SourceDocument.objects.create(organization=org, file=_pdf(f"{n}.pdf"), original_filename=f"{n}.pdf")
        for n in ("a", "b", "c")
    )
    chosen_order = [third_uploaded, first_uploaded, second_uploaded]

    _authenticate(api_client, user)
    response = api_client.post(
        "/api/jobs/", {"document_ids": [str(d.id) for d in chosen_order]}, format="json"
    )

    assert response.status_code == 201, response.data
    assert [d["original_filename"] for d in response.data["documents"]] == ["c.pdf", "a.pdf", "b.pdf"]
    job = PressReviewJob.objects.get(pk=response.data["id"])
    assert [d.original_filename for d in _ordered_documents(job)] == ["c.pdf", "a.pdf", "b.pdf"]


@pytest.mark.django_db
def test_pending_document_can_be_removed(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user)
    document = SourceDocument.objects.create(organization=org, file=_pdf(), original_filename="erreur.pdf")
    stored_path = document.file.path

    _authenticate(api_client, user)
    response = api_client.delete(f"/api/documents/{document.id}/")

    assert response.status_code == 204
    assert not SourceDocument.objects.filter(pk=document.pk).exists()
    import os

    assert not os.path.exists(stored_path)


@pytest.mark.django_db
def test_document_already_used_in_a_review_cannot_be_removed(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user)
    job = PressReviewJob.objects.create(organization=org, title="Revue")
    document = SourceDocument.objects.create(organization=org, job=job, file=_pdf(), original_filename="a.pdf")

    _authenticate(api_client, user)
    assert api_client.delete(f"/api/documents/{document.id}/").status_code == 404
    assert SourceDocument.objects.filter(pk=document.pk).exists()


@pytest.mark.django_db
def test_cannot_remove_another_organizations_document(api_client):
    other_document = SourceDocument.objects.create(
        organization=OrganizationFactory(), file=_pdf(), original_filename="confidentiel.pdf"
    )
    user = UserFactory()
    MembershipFactory(organization=OrganizationFactory(), user=user)

    _authenticate(api_client, user)
    assert api_client.delete(f"/api/documents/{other_document.id}/").status_code == 404
    assert SourceDocument.objects.filter(pk=other_document.pk).exists()


# --- Équipe ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_invitation_returns_a_shareable_link_and_can_be_listed_then_revoked(api_client, settings):
    settings.FRONTEND_BASE_URL = "https://presse.example.cm/"
    org = OrganizationFactory()
    admin = UserFactory()
    MembershipFactory(organization=org, user=admin, role=Membership.Role.ADMIN)
    _authenticate(api_client, admin)

    created = api_client.post("/api/organizations/me/invite/", {"email": "Collegue@Example.com", "role": "member"})
    assert created.status_code == 201, created.data
    invitation = Invitation.objects.get(pk=created.data["id"])
    assert created.data["accept_url"] == f"https://presse.example.cm/invitations/{invitation.token}/accept"

    listed = api_client.get("/api/organizations/me/invitations/")
    assert [item["email"] for item in listed.data] == ["collegue@example.com"]

    assert api_client.delete(f"/api/organizations/me/invitations/{invitation.id}/").status_code == 204
    invitation.refresh_from_db()
    assert invitation.status == Invitation.Status.REVOKED
    assert api_client.get("/api/organizations/me/invitations/").data == []


@pytest.mark.django_db
def test_members_cannot_list_invitation_links(api_client):
    org = OrganizationFactory()
    member = UserFactory()
    MembershipFactory(organization=org, user=member, role=Membership.Role.MEMBER)
    _authenticate(api_client, member)

    assert api_client.get("/api/organizations/me/invitations/").status_code == 403


@pytest.mark.django_db
def test_organization_endpoint_tells_the_frontend_the_current_users_role(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role=Membership.Role.MEMBER)
    _authenticate(api_client, user)

    assert api_client.get("/api/organizations/me/").data["my_role"] == "member"
