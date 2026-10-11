"""Compte en libre-service : connexion insensible à la casse, mot de passe oublié,
changement de mot de passe (fermeture des autres sessions), « Mon compte », et lien de
réinitialisation généré par un owner/admin ou par le staff (à partager sur WhatsApp)."""
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import RequestFactory
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.admin import UserAdmin
from apps.accounts.models import Membership, User
from tests.factories import MembershipFactory, OrganizationFactory, UserFactory

PASSWORD = "testpass1234"
NEW_PASSWORD = "un-nouveau-mot-de-passe-42"
RESET_LINK = re.compile(r"/reinitialiser-mot-de-passe/(?P<uid>[^/\s]+)/(?P<token>[^/\s]+)")


def _authenticate(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")


def _login(client, email, password=PASSWORD):
    response = client.post("/api/auth/token/", {"email": email, "password": password})
    return response


@contextmanager
def _tokens_issued_in_the_past(seconds=30):
    """Les jetons émis dans ce bloc portent un `iat` antérieur (évite qu'un jeton et la
    révocation tombent dans la même seconde, granularité de `iat`)."""
    past = timezone.now() - timedelta(seconds=seconds)
    with mock.patch("rest_framework_simplejwt.tokens.aware_utcnow", return_value=past):
        yield


def _session_cookie(client, email, password=PASSWORD):
    response = _login(client, email, password)
    assert response.status_code == 200, response.data
    return response.cookies["refresh_token"].value


def _refresh(client, cookie):
    client.cookies["refresh_token"] = cookie
    return client.post("/api/auth/token/refresh/")


# --- Connexion ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_ignores_the_case_and_surrounding_spaces_of_the_email(api_client):
    UserFactory(email="jean.ndjock@entreprise.cm")

    response = _login(api_client, "  Jean.Ndjock@Entreprise.CM ")

    assert response.status_code == 200, response.data
    assert "access" in response.data


@pytest.mark.django_db
def test_accounts_are_always_stored_in_lowercase():
    user = User.objects.create_user(email="Awa.Nkoulou@Presse.CM", password=PASSWORD)
    assert user.email == "awa.nkoulou@presse.cm"


@pytest.mark.django_db
def test_legacy_mixed_case_account_still_logs_in_with_its_exact_address(api_client):
    legacy = UserFactory()
    User.objects.filter(pk=legacy.pk).update(email="Ancien.Compte@Example.com")

    assert _login(api_client, "Ancien.Compte@Example.com").status_code == 200
    assert _login(api_client, "ancien.compte@example.com").status_code == 200


@pytest.mark.django_db
def test_registration_refuses_an_email_that_differs_only_by_case(api_client):
    UserFactory(email="deja@client.cm")
    response = api_client.post(
        "/api/auth/register/",
        {
            "email": "DEJA@client.cm",
            "password": "un-mot-de-passe-solide",
            "full_name": "Doublon",
            "organization_name": "Doublon SARL",
            "phone_number": "690000099",
            "accept_terms": True,
        },
    )
    assert response.status_code == 400
    assert response.data["errors"]["email"] == ["Un compte existe déjà avec cet email."]


# --- Mot de passe oublié ---------------------------------------------------------------------


@pytest.mark.django_db
def test_password_reset_request_always_answers_200_and_mails_only_existing_accounts(api_client, settings):
    settings.FRONTEND_BASE_URL = "https://presse.example.cm/"
    UserFactory(email="awa@presse.cm", full_name="Awa")

    known = api_client.post("/api/auth/password/reset/", {"email": "AWA@presse.cm"})
    unknown = api_client.post("/api/auth/password/reset/", {"email": "personne@nulle-part.cm"})

    assert known.status_code == unknown.status_code == 200
    assert known.data["detail"] == unknown.data["detail"]
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["awa@presse.cm"]
    assert "https://presse.example.cm/reinitialiser-mot-de-passe/" in message.body
    assert "Bonjour Awa" in message.body


@pytest.mark.django_db
def test_password_reset_view_is_rate_limited_under_its_own_scope():
    from apps.accounts.views import PasswordResetRequestView

    assert PasswordResetRequestView.throttle_scope == "password_reset"


@pytest.mark.django_db
def test_password_reset_email_failure_is_not_revealed(api_client):
    UserFactory(email="awa@presse.cm")
    with mock.patch("apps.accounts.services.send_mail", side_effect=OSError("SMTP injoignable")):
        response = api_client.post("/api/auth/password/reset/", {"email": "awa@presse.cm"})
    assert response.status_code == 200


def _reset_link_parts():
    match = RESET_LINK.search(mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match["uid"], match["token"]


@pytest.mark.django_db
def test_reset_link_sets_a_new_password_once_and_closes_every_session(api_client, client):
    user = UserFactory(email="awa@presse.cm")
    with _tokens_issued_in_the_past():
        old_session = _session_cookie(client, "awa@presse.cm")
    api_client.post("/api/auth/password/reset/", {"email": "awa@presse.cm"})
    uid, token = _reset_link_parts()

    response = api_client.post(
        "/api/auth/password/reset/confirm/", {"uid": uid, "token": token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert _refresh(client, old_session).status_code == 401
    # Lien à usage unique.
    again = api_client.post(
        "/api/auth/password/reset/confirm/", {"uid": uid, "token": token, "new_password": "encore-un-autre-99"}
    )
    assert again.status_code == 400
    assert again.data["detail"] == "Ce lien de réinitialisation est invalide ou a expiré. Demandez-en un nouveau."
    assert _login(api_client, "awa@presse.cm", NEW_PASSWORD).status_code == 200


@pytest.mark.django_db
def test_reset_confirm_applies_the_password_validators(api_client):
    UserFactory(email="awa@presse.cm")
    api_client.post("/api/auth/password/reset/", {"email": "awa@presse.cm"})
    uid, token = _reset_link_parts()

    response = api_client.post(
        "/api/auth/password/reset/confirm/", {"uid": uid, "token": token, "new_password": "123456789012"}
    )

    assert response.status_code == 400
    assert response.data["errors"]["new_password"]


@pytest.mark.django_db
@pytest.mark.parametrize("uid", ["pas-un-uid", "MTIz"])
def test_reset_confirm_with_a_forged_link_is_refused_cleanly(api_client, uid):
    UserFactory()
    response = api_client.post(
        "/api/auth/password/reset/confirm/", {"uid": uid, "token": "abc-123", "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400
    assert response.data["detail"] == "Ce lien de réinitialisation est invalide ou a expiré. Demandez-en un nouveau."


# --- Changement de mot de passe ------------------------------------------------------------------


@pytest.mark.django_db
def test_password_change_closes_other_sessions_but_keeps_the_current_one(api_client, client):
    from django.test import Client

    user = UserFactory(email="awa@presse.cm")
    other_device = Client()
    with _tokens_issued_in_the_past():
        other_session = _session_cookie(other_device, "awa@presse.cm")
        # Un refresh token issu d'une rotation n'est pas connu de la liste noire de simplejwt :
        # il doit tout de même être refusé.
        rotated = _refresh(other_device, other_session)
        assert rotated.status_code == 200
        rotated_session = rotated.cookies["refresh_token"].value

    _authenticate(api_client, user)
    response = api_client.post(
        "/api/auth/password/change/", {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 200, response.data
    assert "access" in response.data
    current_session = response.cookies["refresh_token"].value
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    assert _refresh(other_device, rotated_session).status_code == 401
    assert _refresh(Client(), current_session).status_code == 200


@pytest.mark.django_db
def test_password_change_requires_the_current_password(api_client):
    user = UserFactory()
    _authenticate(api_client, user)

    response = api_client.post(
        "/api/auth/password/change/", {"current_password": "mauvais-mot-de-passe", "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Mot de passe actuel incorrect."
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_password_change_rejects_a_weak_password(api_client):
    user = UserFactory()
    _authenticate(api_client, user)

    response = api_client.post("/api/auth/password/change/", {"current_password": PASSWORD, "new_password": "court"})

    assert response.status_code == 400
    assert response.data["errors"]["new_password"]


@pytest.mark.django_db
def test_refresh_is_refused_for_a_deactivated_account(client):
    user = UserFactory(email="parti@presse.cm")
    cookie = _session_cookie(client, "parti@presse.cm")
    User.objects.filter(pk=user.pk).update(is_active=False)

    assert _refresh(client, cookie).status_code == 401


# --- Mon compte ------------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_can_rename_himself_but_not_change_his_email(api_client):
    user = UserFactory(email="awa@presse.cm", full_name="Awa")
    _authenticate(api_client, user)

    response = api_client.patch("/api/auth/me/", {"full_name": "  Awa Nkoulou ", "email": "pirate@x.cm"})

    assert response.status_code == 200, response.data
    assert response.data["full_name"] == "Awa Nkoulou"
    user.refresh_from_db()
    assert user.email == "awa@presse.cm"


@pytest.mark.django_db
def test_user_name_cannot_be_emptied(api_client):
    user = UserFactory()
    _authenticate(api_client, user)
    assert api_client.patch("/api/auth/me/", {"full_name": " "}).status_code == 400


# --- Lien de réinitialisation à partager (owner/admin, staff) --------------------------------------


def _team(owner_role=Membership.Role.OWNER):
    org = OrganizationFactory()
    owner = UserFactory()
    MembershipFactory(organization=org, user=owner, role=owner_role)
    return org, owner


@pytest.mark.django_db
def test_owner_generates_a_shareable_reset_link_for_a_member(api_client, client, settings):
    settings.FRONTEND_BASE_URL = "https://presse.example.cm"
    org, owner = _team()
    member = UserFactory(email="membre@presse.cm")
    membership = MembershipFactory(organization=org, user=member)
    _authenticate(api_client, owner)

    response = api_client.post(f"/api/organizations/me/members/{membership.id}/password-reset-link/")

    assert response.status_code == 200, response.data
    match = RESET_LINK.search(response.data["reset_url"])
    assert response.data["reset_url"].startswith("https://presse.example.cm/reinitialiser-mot-de-passe/")
    confirm = client.post(
        "/api/auth/password/reset/confirm/",
        {"uid": match["uid"], "token": match["token"], "new_password": NEW_PASSWORD},
        content_type="application/json",
    )
    assert confirm.status_code == 200
    member.refresh_from_db()
    assert member.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_admin_cannot_generate_a_reset_link_for_an_owner_or_another_admin(api_client):
    org, owner = _team()
    admin = UserFactory()
    MembershipFactory(organization=org, user=admin, role=Membership.Role.ADMIN)
    other_admin = MembershipFactory(organization=org, role=Membership.Role.ADMIN)
    owner_membership = Membership.objects.get(organization=org, user=owner)
    _authenticate(api_client, admin)

    for target in (owner_membership, other_admin):
        response = api_client.post(f"/api/organizations/me/members/{target.id}/password-reset-link/")
        assert response.status_code == 403
        assert response.data["detail"].startswith("Seul un propriétaire peut")


@pytest.mark.django_db
def test_reset_link_is_refused_for_an_account_that_belongs_to_another_organization(api_client):
    """Sinon le propriétaire d'une organisation pourrait prendre la main sur un compte qui a
    accès aux données d'une autre organisation."""
    org, owner = _team()
    member = UserFactory()
    membership = MembershipFactory(organization=org, user=member)
    MembershipFactory(organization=OrganizationFactory(), user=member, role=Membership.Role.OWNER)
    _authenticate(api_client, owner)

    response = api_client.post(f"/api/organizations/me/members/{membership.id}/password-reset-link/")

    assert response.status_code == 403
    assert "WhatsApp" in response.data["detail"]


@pytest.mark.django_db
def test_members_cannot_generate_reset_links(api_client):
    org, _owner = _team()
    member = UserFactory()
    MembershipFactory(organization=org, user=member)
    target = MembershipFactory(organization=org)
    _authenticate(api_client, member)

    assert api_client.post(f"/api/organizations/me/members/{target.id}/password-reset-link/").status_code == 403


@pytest.mark.django_db
def test_staff_admin_action_shows_a_reset_link():
    staff = UserFactory(is_staff=True, is_superuser=True)
    target = UserFactory(email="client@presse.cm")
    request = RequestFactory().post("/admin/accounts/user/")
    request.user = staff
    request.session = {}
    request._messages = FallbackStorage(request)

    UserAdmin(User, AdminSite()).generate_password_reset_links(request, User.objects.filter(pk=target.pk))

    texts = [str(m) for m in request._messages]
    assert len(texts) == 1
    assert "client@presse.cm" in texts[0]
    assert "/reinitialiser-mot-de-passe/" in texts[0]
