"""Inscription (CGU, numéro WhatsApp, un seul essai par numéro), places de la formule
(membres + invitations en attente), export des données et fermeture de l'organisation."""
import json
from datetime import timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.admin import OrganizationAdmin
from apps.accounts.models import Invitation, Membership, Organization, User
from apps.accounts.services import (
    TRIAL_ALREADY_USED_MESSAGE,
    create_invitation,
    register_organization_owner,
    seats_available,
)
from apps.billing.models import Invoice, Subscription
from apps.press_review.models import GeneratedReview, Highlight, PressReviewJob, SourceDocument
from tests.factories import (
    DetectionCategoryFactory,
    MembershipFactory,
    OrganizationFactory,
    PlanFactory,
    SubscriptionFactory,
    UserFactory,
)

OWNER, ADMIN, MEMBER = Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MEMBER


def _authenticate(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")


def _registration(**overrides):
    data = {
        "email": "awa@presse-plus.cm",
        "password": "un-mot-de-passe-solide",
        "full_name": "Awa Nkoulou",
        "organization_name": "Presse Plus SARL",
        "phone_number": "6 93 42 79 13",
        "accept_terms": True,
    }
    data.update(overrides)
    return data


@pytest.fixture
def starter_plan(db):
    return PlanFactory(code="starter", name="Starter", max_reviews_per_month=10, max_seats=3)


# --- Inscription -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_registration_records_terms_acceptance_and_the_normalized_phone(api_client, starter_plan, settings):
    settings.TERMS_VERSION = "2026-10-cgu-v1"

    response = api_client.post("/api/auth/register/", _registration())

    assert response.status_code == 201, response.data
    assert response.data["trial_granted"] is True
    assert response.data["trial_notice"] is None
    user = User.objects.get(email="awa@presse-plus.cm")
    assert user.terms_version == "2026-10-cgu-v1"
    assert timezone.now() - user.accepted_terms_at < timedelta(minutes=1)
    assert Organization.objects.get(name="Presse Plus SARL").contact_phone == "+237693427913"


@pytest.mark.django_db
@pytest.mark.parametrize("accept_terms", [False, None])
def test_registration_requires_accepting_the_terms(api_client, starter_plan, accept_terms):
    data = _registration(accept_terms=accept_terms)
    if accept_terms is None:
        del data["accept_terms"]

    response = api_client.post("/api/auth/register/", data)

    assert response.status_code == 400
    assert "accept_terms" in response.data["errors"]
    assert not User.objects.filter(email="awa@presse-plus.cm").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("phone", ["", "12", "06 12 34 56 78", "+237 6934"])
def test_registration_requires_a_valid_whatsapp_number(api_client, starter_plan, phone):
    response = api_client.post("/api/auth/register/", _registration(phone_number=phone))

    assert response.status_code == 400
    assert "phone_number" in response.data["errors"]


@pytest.mark.django_db
def test_only_one_free_trial_per_phone_number_whatever_its_format(api_client, starter_plan):
    first = api_client.post("/api/auth/register/", _registration())
    assert first.data["trial_granted"] is True

    second = api_client.post(
        "/api/auth/register/",
        _registration(email="autre@ailleurs.cm", organization_name="Autre SARL", phone_number="+237 693-42-79-13"),
    )

    assert second.status_code == 201, second.data
    assert second.data["trial_granted"] is False
    assert second.data["trial_notice"] == TRIAL_ALREADY_USED_MESSAGE
    assert not Subscription.objects.filter(organization__name="Autre SARL").exists()
    # Le compte est bien créé : l'équipe active l'abonnement à la main.
    assert Membership.objects.get(organization__name="Autre SARL").role == OWNER


@pytest.mark.django_db
def test_staff_can_still_grant_a_trial_from_the_admin(starter_plan):
    register_organization_owner(
        email="a@a.cm", password="un-mot-de-passe-solide", full_name="A", organization_name="A",
        phone_number="690000001",
    )
    _user, refused, _m = register_organization_owner(
        email="b@b.cm", password="un-mot-de-passe-solide", full_name="B", organization_name="B",
        phone_number="690000001",
    )
    assert not Subscription.objects.filter(organization=refused).exists()
    request = RequestFactory().post("/admin/accounts/organization/")
    request.user = UserFactory(is_staff=True, is_superuser=True)
    request.session = {}
    request._messages = FallbackStorage(request)

    OrganizationAdmin(Organization, AdminSite()).grant_trial(request, Organization.objects.filter(pk=refused.pk))

    assert Subscription.objects.get(organization=refused).status == Subscription.Status.TRIALING


@pytest.mark.django_db
def test_invited_member_must_accept_the_terms_too(api_client):
    org = OrganizationFactory()
    owner = UserFactory()
    MembershipFactory(organization=org, user=owner, role=OWNER)
    invitation = create_invitation(organization=org, email="invite@presse.cm", role=MEMBER, invited_by=owner)
    url = f"/api/auth/invitations/{invitation.token}/register/"

    refused = api_client.post(url, {"full_name": "Invité", "password": "un-mot-de-passe-solide"})
    accepted = api_client.post(url, {"full_name": "Invité", "password": "un-mot-de-passe-solide", "accept_terms": True})

    assert refused.status_code == 400
    assert accepted.status_code == 201, accepted.data
    assert User.objects.get(email="invite@presse.cm").accepted_terms_at is not None


# --- Places de la formule ----------------------------------------------------------------------


def _org_with_seats(max_seats, members=1):
    org = OrganizationFactory()
    SubscriptionFactory(organization=org, plan=PlanFactory(max_seats=max_seats))
    owner = UserFactory()
    MembershipFactory(organization=org, user=owner, role=OWNER)
    for _ in range(members - 1):
        MembershipFactory(organization=org)
    return org, owner


@pytest.mark.django_db
def test_pending_invitations_count_against_the_plan_seats(api_client):
    org, owner = _org_with_seats(max_seats=3, members=2)
    _authenticate(api_client, owner)

    first = api_client.post("/api/organizations/me/invite/", {"email": "un@presse.cm", "role": MEMBER})
    second = api_client.post("/api/organizations/me/invite/", {"email": "deux@presse.cm", "role": MEMBER})

    assert first.status_code == 201
    assert second.status_code == 400
    assert second.data["detail"].startswith("Toutes les places de votre formule sont occupées (3 / 3")
    assert "WhatsApp" in second.data["detail"]
    seats = api_client.get("/api/organizations/me/seats/").data
    assert seats == {"members": 2, "pending_invitations": 1, "used": 3, "limit": 3, "available": 0}


@pytest.mark.django_db
def test_reinviting_the_same_person_renews_the_invitation_without_taking_a_seat(api_client):
    org, owner = _org_with_seats(max_seats=2)
    invitation = create_invitation(organization=org, email="un@presse.cm", role=MEMBER, invited_by=owner)
    Invitation.objects.filter(pk=invitation.pk).update(expires_at=timezone.now() + timedelta(hours=1))
    _authenticate(api_client, owner)

    response = api_client.post("/api/organizations/me/invite/", {"email": "un@presse.cm", "role": MEMBER})

    assert response.status_code == 201, response.data
    invitation.refresh_from_db()
    assert invitation.expires_at > timezone.now() + timedelta(days=6)


@pytest.mark.django_db
def test_expired_or_revoked_invitations_free_their_seat(api_client):
    org, owner = _org_with_seats(max_seats=2)
    expired = create_invitation(organization=org, email="vieux@presse.cm", role=MEMBER, invited_by=owner)
    Invitation.objects.filter(pk=expired.pk).update(expires_at=timezone.now() - timedelta(days=1))
    _authenticate(api_client, owner)

    assert api_client.post("/api/organizations/me/invite/", {"email": "neuf@presse.cm", "role": MEMBER}).status_code == 201


@pytest.mark.django_db
def test_acceptance_is_refused_when_the_plan_was_reduced_since_the_invitation(api_client):
    org, owner = _org_with_seats(max_seats=3)
    invitation = create_invitation(organization=org, email="invite@presse.cm", role=MEMBER, invited_by=owner)
    MembershipFactory(organization=org)
    MembershipFactory(organization=org)  # 3 membres sur 3 : plus de place
    invited = UserFactory(email="invite@presse.cm")
    _authenticate(api_client, invited)

    response = api_client.post(f"/api/auth/invitations/{invitation.token}/accept/")

    assert response.status_code == 400
    assert "a atteint le nombre de places de sa formule (3)" in response.data["detail"]
    assert not Membership.objects.filter(organization=org, user=invited).exists()


@pytest.mark.django_db
def test_the_last_reserved_seat_can_be_taken_by_its_invitation(api_client):
    org, owner = _org_with_seats(max_seats=3, members=2)
    invitation = create_invitation(organization=org, email="invite@presse.cm", role=MEMBER, invited_by=owner)
    assert seats_available(org) == 0
    assert seats_available(org, exclude_invitation=invitation) == 1
    invited = UserFactory(email="invite@presse.cm")
    _authenticate(api_client, invited)

    response = api_client.post(f"/api/auth/invitations/{invitation.token}/accept/")

    assert response.status_code == 200, response.data
    assert Membership.objects.filter(organization=org, user=invited).exists()


@pytest.mark.django_db
def test_seats_available_is_none_without_subscription():
    assert seats_available(OrganizationFactory()) is None


@pytest.mark.django_db
def test_invited_registration_is_refused_when_the_organization_is_full(api_client):
    org, owner = _org_with_seats(max_seats=2)
    invitation = create_invitation(organization=org, email="invite@presse.cm", role=MEMBER, invited_by=owner)
    MembershipFactory(organization=org)

    response = api_client.post(
        f"/api/auth/invitations/{invitation.token}/register/",
        {"full_name": "Invité", "password": "un-mot-de-passe-solide", "accept_terms": True},
    )

    assert response.status_code == 400
    assert not User.objects.filter(email="invite@presse.cm").exists()


@pytest.mark.django_db
def test_seats_are_unlimited_without_subscription(api_client):
    org = OrganizationFactory()
    owner = UserFactory()
    MembershipFactory(organization=org, user=owner, role=OWNER)
    _authenticate(api_client, owner)

    assert api_client.get("/api/organizations/me/seats/").data["limit"] is None
    assert api_client.post("/api/organizations/me/invite/", {"email": "x@presse.cm", "role": MEMBER}).status_code == 201


# --- Export des données ------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_exports_the_organization_data_without_prices(api_client, tmp_path):
    org = OrganizationFactory(name="Presse Plus")
    owner = UserFactory(email="owner@presse.cm")
    MembershipFactory(organization=org, user=owner, role=OWNER)
    subscription = SubscriptionFactory(organization=org, plan=PlanFactory(name="Pro", price_amount=150000))
    Invoice.objects.create(
        organization=org,
        subscription=subscription,
        provider=Subscription.Provider.BANK_TRANSFER,
        amount=150000,
        period_start=timezone.now(),
        period_end=timezone.now() + timedelta(days=30),
    )
    job = PressReviewJob.objects.create(organization=org, title="Revue du lundi", created_by=owner)
    SourceDocument.objects.create(organization=org, job=job, file="x.pdf", original_filename="une.pdf")
    GeneratedReview.objects.create(job=job, summary_markdown="# Revue", structured={"sections": []})
    Highlight.objects.create(job=job, category=DetectionCategoryFactory(name="Risque"), excerpt="Extrait cité")
    other = PressReviewJob.objects.create(organization=OrganizationFactory(), title="Autre organisation")
    _authenticate(api_client, owner)

    response = api_client.get("/api/organizations/me/export/")

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith('attachment; filename="revue-de-presse-presse-plus-')
    data = json.loads(response.content)
    assert data["organization"]["name"] == "Presse Plus"
    assert [m["email"] for m in data["members"]] == ["owner@presse.cm"]
    assert [r["title"] for r in data["reviews"]] == ["Revue du lundi"]
    review = data["reviews"][0]
    assert review["review"]["summary_markdown"] == "# Revue"
    assert review["highlights"][0]["excerpt"] == "Extrait cité"
    assert review["documents"][0]["original_filename"] == "une.pdf"
    assert other.title not in json.dumps(data)
    assert len(data["invoices"]) == 1
    assert "150000" not in json.dumps(data) and "amount" not in data["invoices"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("role", [ADMIN, MEMBER])
def test_only_owners_export_or_close(api_client, role):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role=role)
    _authenticate(api_client, user)

    assert api_client.get("/api/organizations/me/export/").status_code == 403
    assert api_client.post("/api/organizations/me/close/", {"confirm_name": org.name}).status_code == 403
    org.refresh_from_db()
    assert org.closed_at is None


# --- Fermeture de l'organisation -----------------------------------------------------------------


@pytest.mark.django_db
def test_closing_requires_typing_the_organization_name(api_client):
    org = OrganizationFactory(name="Presse Plus")
    owner = UserFactory()
    MembershipFactory(organization=org, user=owner, role=OWNER)
    _authenticate(api_client, owner)

    response = api_client.post("/api/organizations/me/close/", {"confirm_name": "Autre nom"})

    assert response.status_code == 400
    org.refresh_from_db()
    assert org.closed_at is None


@pytest.mark.django_db
def test_closed_organization_is_no_longer_accessible_and_its_invitations_die(api_client):
    org = OrganizationFactory(name="Presse Plus")
    owner, member = UserFactory(), UserFactory()
    MembershipFactory(organization=org, user=owner, role=OWNER)
    MembershipFactory(organization=org, user=member, role=MEMBER)
    invitation = create_invitation(organization=org, email="invite@presse.cm", role=MEMBER, invited_by=owner)
    _authenticate(api_client, owner)

    response = api_client.post(
        "/api/organizations/me/close/", {"confirm_name": " presse plus ", "reason": "Fin du contrat"}
    )

    assert response.status_code == 200, response.data
    org.refresh_from_db()
    assert org.closed_at is not None
    assert org.closed_by == owner
    assert org.closure_reason == "Fin du contrat"
    invitation.refresh_from_db()
    assert invitation.status == Invitation.Status.REVOKED
    # Les données restent en base (purge par le staff), mais plus personne n'y accède.
    assert Organization.objects.filter(pk=org.pk).exists()
    for user in (owner, member):
        _authenticate(api_client, user)
        assert api_client.get("/api/jobs/").status_code == 404
        assert api_client.get("/api/jobs/", HTTP_X_ORGANIZATION_ID=str(org.id)).status_code == 403
        assert api_client.get("/api/organizations/").data == []
    assert api_client.get(f"/api/auth/invitations/{invitation.token}/").status_code == 404


@pytest.mark.django_db
def test_closing_one_organization_keeps_access_to_the_others(api_client):
    user = UserFactory()
    closed = OrganizationFactory(name="Fermée")
    kept = OrganizationFactory(name="Gardée")
    MembershipFactory(organization=closed, user=user, role=OWNER)
    MembershipFactory(organization=kept, user=user, role=MEMBER)
    _authenticate(api_client, user)

    api_client.post("/api/organizations/me/close/", {"confirm_name": "Fermée"}, HTTP_X_ORGANIZATION_ID=str(closed.id))

    assert [o["name"] for o in api_client.get("/api/organizations/").data] == ["Gardée"]
    # Une seule organisation active : plus besoin d'en-tête.
    assert api_client.get("/api/organizations/me/").data["name"] == "Gardée"


@pytest.mark.django_db
def test_staff_can_reopen_a_closed_organization():
    org = OrganizationFactory(closed_at=timezone.now(), closure_reason="Erreur")
    request = RequestFactory().post("/admin/accounts/organization/")
    request.user = UserFactory(is_staff=True, is_superuser=True)
    request.session = {}
    request._messages = FallbackStorage(request)

    OrganizationAdmin(Organization, AdminSite()).reopen(request, Organization.objects.filter(pk=org.pk))

    org.refresh_from_db()
    assert org.closed_at is None
