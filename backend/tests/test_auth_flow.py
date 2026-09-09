import pytest


@pytest.mark.django_db
def test_register_creates_owner_and_sets_refresh_cookie(api_client):
    response = api_client.post(
        "/api/auth/register/",
        {
            "email": "founder@example.com",
            "password": "a-very-strong-pass-1",
            "full_name": "Founder",
            "organization_name": "Acme SARL",
        },
    )

    assert response.status_code == 201
    assert "access" in response.data
    assert response.data["organization"]["name"] == "Acme SARL"
    assert "refresh_token" in response.cookies
    assert response.cookies["refresh_token"]["httponly"]


@pytest.mark.django_db
def test_login_then_refresh_cycle(api_client):
    from apps.accounts.services import register_organization_owner

    register_organization_owner(
        email="owner@example.com", password="a-very-strong-pass-1", full_name="Owner", organization_name="Org"
    )

    login_response = api_client.post(
        "/api/auth/token/", {"email": "owner@example.com", "password": "a-very-strong-pass-1"}
    )
    assert login_response.status_code == 200
    assert "access" in login_response.data

    api_client.cookies["refresh_token"] = login_response.cookies["refresh_token"].value

    refresh_response = api_client.post("/api/auth/token/refresh/")
    assert refresh_response.status_code == 200
    assert "access" in refresh_response.data


@pytest.mark.django_db
def test_login_with_wrong_password_is_rejected(api_client):
    from apps.accounts.services import register_organization_owner

    register_organization_owner(
        email="owner2@example.com", password="a-very-strong-pass-1", full_name="Owner", organization_name="Org"
    )

    response = api_client.post("/api/auth/token/", {"email": "owner2@example.com", "password": "wrong-password"})

    assert response.status_code == 401


@pytest.mark.django_db
def test_refresh_without_cookie_returns_404(api_client):
    response = api_client.post("/api/auth/token/refresh/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_refresh_with_garbage_cookie_returns_401_not_500(api_client):
    """Régression : simplejwt lève TokenError (pas une exception DRF) sur un refresh
    token invalide ; non interceptée, ça remontait en 500 au lieu d'un 401 propre."""
    api_client.cookies["refresh_token"] = "not-a-valid-jwt"

    response = api_client.post("/api/auth/token/refresh/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_invitation_register_joins_existing_organization_not_a_new_one(api_client):
    from apps.accounts.models import Membership, Organization
    from apps.accounts.services import create_invitation, register_organization_owner

    owner, org, _membership = register_organization_owner(
        email="owner3@example.com", password="a-very-strong-pass-1", full_name="Owner", organization_name="Acme"
    )
    invitation = create_invitation(
        organization=org, email="invitee@example.com", role=Membership.Role.MEMBER, invited_by=owner
    )
    orgs_before = Organization.objects.count()

    response = api_client.post(
        f"/api/auth/invitations/{invitation.token}/register/",
        {"full_name": "Invitee", "password": "another-strong-pass-1"},
    )

    assert response.status_code == 201
    assert Organization.objects.count() == orgs_before
    membership = Membership.objects.get(organization=org, user__email="invitee@example.com")
    assert membership.role == Membership.Role.MEMBER
