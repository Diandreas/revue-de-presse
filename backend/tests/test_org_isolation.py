import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership
from apps.press_review.models import PressReviewJob
from tests.factories import MembershipFactory, OrganizationFactory, UserFactory


def _authenticate(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")


@pytest.mark.django_db
def test_user_cannot_access_another_organizations_job(api_client):
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user_a = UserFactory()
    MembershipFactory(organization=org_a, user=user_a)
    job_b = PressReviewJob.objects.create(organization=org_b, title="Confidentiel org B")

    _authenticate(api_client, user_a)
    response = api_client.get(f"/api/jobs/{job_b.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_ambiguous_organization_without_header_is_rejected(api_client):
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org_a, user=user)
    MembershipFactory(organization=org_b, user=user)

    _authenticate(api_client, user)
    response = api_client.get("/api/jobs/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_organization_header_selects_the_right_tenant(api_client):
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org_a, user=user)
    MembershipFactory(organization=org_b, user=user)
    PressReviewJob.objects.create(organization=org_a, title="Job A")
    PressReviewJob.objects.create(organization=org_b, title="Job B")

    _authenticate(api_client, user)
    response = api_client.get("/api/jobs/", HTTP_X_ORGANIZATION_ID=str(org_a.id))

    assert response.status_code == 200
    titles = {item["title"] for item in response.data["results"]}
    assert titles == {"Job A"}


@pytest.mark.django_db
def test_non_admin_member_cannot_invite(api_client):
    org = OrganizationFactory()
    user = UserFactory()
    MembershipFactory(organization=org, user=user, role="member")

    _authenticate(api_client, user)
    response = api_client.post("/api/organizations/me/invite/", {"email": "new@example.com", "role": "member"})

    assert response.status_code == 403


@pytest.mark.django_db
def test_unauthenticated_request_is_rejected(api_client):
    response = api_client.get("/api/jobs/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_organization_admin_can_invite(api_client):
    org = OrganizationFactory()
    admin = UserFactory()
    MembershipFactory(organization=org, user=admin, role=Membership.Role.ADMIN)

    _authenticate(api_client, admin)
    response = api_client.post("/api/organizations/me/invite/", {"email": "new@example.com", "role": "member"})

    assert response.status_code == 201


@pytest.mark.django_db
def test_validation_error_message_reaches_the_client_verbatim(api_client):
    """Régression : le exception handler custom (apps/core/exceptions.py) ne doit
    pas remplacer un message ValidationError explicite par un texte générique."""
    org = OrganizationFactory()
    admin = UserFactory()
    MembershipFactory(organization=org, user=admin, role=Membership.Role.ADMIN)
    existing_member = UserFactory(email="existing@example.com")
    MembershipFactory(organization=org, user=existing_member, role=Membership.Role.MEMBER)

    _authenticate(api_client, admin)
    response = api_client.post("/api/organizations/me/invite/", {"email": "existing@example.com", "role": "member"})

    assert response.status_code == 400
    assert response.data["detail"] == "Cette personne est déjà membre de l'organisation."
