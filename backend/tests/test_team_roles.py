"""Hiérarchie des rôles (seul un owner gère owners et admins), changement de rôle,
transfert de propriété, départ volontaire, et comptes membres de plusieurs organisations."""
import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Invitation, Membership
from apps.accounts.services import create_invitation
from apps.press_review.models import PressReviewJob
from tests.factories import MembershipFactory, OrganizationFactory, UserFactory

OWNER, ADMIN, MEMBER = Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.MEMBER


def _authenticate(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")


@pytest.fixture
def team(db):
    """Une organisation avec un owner, un admin et un membre."""
    org = OrganizationFactory(name="Presse Plus")
    owner, admin, member = UserFactory(), UserFactory(), UserFactory()
    return {
        "org": org,
        "owner": owner,
        "admin": admin,
        "member": member,
        "owner_m": MembershipFactory(organization=org, user=owner, role=OWNER),
        "admin_m": MembershipFactory(organization=org, user=admin, role=ADMIN),
        "member_m": MembershipFactory(organization=org, user=member, role=MEMBER),
    }


# --- Invitations -------------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("role", [ADMIN, OWNER])
def test_admin_cannot_invite_an_admin_or_an_owner(api_client, team, role):
    _authenticate(api_client, team["admin"])

    response = api_client.post("/api/organizations/me/invite/", {"email": "nouveau@presse.cm", "role": role})

    assert response.status_code == 403
    assert response.data["detail"] == "Seul un propriétaire peut inviter un administrateur ou un propriétaire."
    assert not Invitation.objects.filter(email="nouveau@presse.cm").exists()


@pytest.mark.django_db
def test_admin_can_invite_a_member_and_owner_can_invite_an_admin(api_client, team):
    _authenticate(api_client, team["admin"])
    assert api_client.post("/api/organizations/me/invite/", {"email": "m@presse.cm", "role": MEMBER}).status_code == 201

    _authenticate(api_client, team["owner"])
    assert api_client.post("/api/organizations/me/invite/", {"email": "a@presse.cm", "role": ADMIN}).status_code == 201


@pytest.mark.django_db
def test_admin_cannot_revoke_an_admin_invitation(api_client, team):
    invitation = create_invitation(organization=team["org"], email="a@presse.cm", role=ADMIN, invited_by=team["owner"])
    _authenticate(api_client, team["admin"])

    response = api_client.delete(f"/api/organizations/me/invitations/{invitation.id}/")

    assert response.status_code == 403
    invitation.refresh_from_db()
    assert invitation.status == Invitation.Status.PENDING


# --- Retrait -----------------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_cannot_remove_the_owner_or_another_admin(api_client, team):
    other_admin = MembershipFactory(organization=team["org"], role=ADMIN)
    _authenticate(api_client, team["admin"])

    for target in (team["owner_m"], other_admin):
        response = api_client.delete(f"/api/organizations/me/members/{target.id}/")
        assert response.status_code == 403
        assert response.data["detail"] == "Seul un propriétaire peut retirer un administrateur ou un propriétaire."
    assert Membership.objects.filter(id__in=[team["owner_m"].id, other_admin.id]).count() == 2


@pytest.mark.django_db
def test_admin_removes_a_member_and_owner_removes_an_admin(api_client, team):
    _authenticate(api_client, team["admin"])
    assert api_client.delete(f"/api/organizations/me/members/{team['member_m'].id}/").status_code == 204

    _authenticate(api_client, team["owner"])
    assert api_client.delete(f"/api/organizations/me/members/{team['admin_m'].id}/").status_code == 204
    assert list(Membership.objects.filter(organization=team["org"]).values_list("role", flat=True)) == [OWNER]


@pytest.mark.django_db
def test_nobody_removes_himself_through_the_member_endpoint(api_client, team):
    _authenticate(api_client, team["admin"])
    response = api_client.delete(f"/api/organizations/me/members/{team['admin_m'].id}/")
    assert response.status_code == 400
    assert "Quitter l'organisation" in response.data["detail"]


@pytest.mark.django_db
def test_unknown_member_returns_404(api_client, team):
    _authenticate(api_client, team["owner"])
    other_org_membership = MembershipFactory(organization=OrganizationFactory())
    assert api_client.delete(f"/api/organizations/me/members/{other_org_membership.id}/").status_code == 404


# --- Changement de rôle --------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_promotes_a_member_to_admin(api_client, team):
    _authenticate(api_client, team["owner"])

    response = api_client.patch(f"/api/organizations/me/members/{team['member_m'].id}/", {"role": ADMIN})

    assert response.status_code == 200, response.data
    assert response.data["role"] == ADMIN
    team["member_m"].refresh_from_db()
    assert team["member_m"].role == ADMIN


@pytest.mark.django_db
def test_admin_cannot_promote_a_member_nor_demote_another_admin(api_client, team):
    other_admin = MembershipFactory(organization=team["org"], role=ADMIN)
    _authenticate(api_client, team["admin"])

    promote = api_client.patch(f"/api/organizations/me/members/{team['member_m'].id}/", {"role": ADMIN})
    demote = api_client.patch(f"/api/organizations/me/members/{other_admin.id}/", {"role": MEMBER})
    make_owner = api_client.patch(f"/api/organizations/me/members/{team['admin_m'].id}/", {"role": OWNER})

    assert promote.status_code == demote.status_code == make_owner.status_code == 403
    assert promote.data["detail"] == "Seul un propriétaire peut nommer un administrateur ou un propriétaire."
    team["member_m"].refresh_from_db()
    assert team["member_m"].role == MEMBER


@pytest.mark.django_db
def test_members_cannot_change_roles(api_client, team):
    _authenticate(api_client, team["member"])
    response = api_client.patch(f"/api/organizations/me/members/{team['admin_m'].id}/", {"role": MEMBER})
    assert response.status_code == 403


@pytest.mark.django_db
def test_last_owner_cannot_be_demoted(api_client, team):
    _authenticate(api_client, team["owner"])

    response = api_client.patch(f"/api/organizations/me/members/{team['owner_m'].id}/", {"role": ADMIN})

    assert response.status_code == 400
    assert "dernier propriétaire" in response.data["detail"]


@pytest.mark.django_db
def test_invalid_role_is_rejected(api_client, team):
    _authenticate(api_client, team["owner"])
    response = api_client.patch(f"/api/organizations/me/members/{team['member_m'].id}/", {"role": "superadmin"})
    assert response.status_code == 400


# --- Transfert de propriété ----------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_transfers_ownership_and_becomes_admin(api_client, team):
    _authenticate(api_client, team["owner"])

    response = api_client.post(
        "/api/organizations/me/transfer-ownership/", {"membership_id": str(team["member_m"].id)}
    )

    assert response.status_code == 200, response.data
    team["member_m"].refresh_from_db()
    team["owner_m"].refresh_from_db()
    assert team["member_m"].role == OWNER
    assert team["owner_m"].role == ADMIN


@pytest.mark.django_db
def test_admin_cannot_transfer_ownership(api_client, team):
    _authenticate(api_client, team["admin"])
    response = api_client.post(
        "/api/organizations/me/transfer-ownership/", {"membership_id": str(team["admin_m"].id)}
    )
    assert response.status_code == 403
    team["admin_m"].refresh_from_db()
    assert team["admin_m"].role == ADMIN


# --- Quitter l'organisation ----------------------------------------------------------------------


@pytest.mark.django_db
def test_member_leaves_the_organization(api_client, team):
    _authenticate(api_client, team["member"])

    assert api_client.post("/api/organizations/me/leave/").status_code == 204
    assert not Membership.objects.filter(id=team["member_m"].id).exists()
    # Plus d'organisation : message clair, avec un code exploitable par le frontend.
    response = api_client.get("/api/organizations/me/")
    assert response.status_code == 404
    assert response.data["code"] == "no_organization"
    assert api_client.get("/api/organizations/").data == []


@pytest.mark.django_db
def test_last_owner_cannot_leave(api_client, team):
    _authenticate(api_client, team["owner"])

    response = api_client.post("/api/organizations/me/leave/")

    assert response.status_code == 400
    assert response.data["detail"].startswith("Vous êtes le dernier propriétaire")
    assert Membership.objects.filter(id=team["owner_m"].id).exists()


@pytest.mark.django_db
def test_an_owner_can_leave_when_another_owner_remains(api_client, team):
    MembershipFactory(organization=team["org"], role=OWNER)
    _authenticate(api_client, team["owner"])
    assert api_client.post("/api/organizations/me/leave/").status_code == 204


# --- Plusieurs organisations ----------------------------------------------------------------------


@pytest.mark.django_db
def test_user_lists_his_organizations_with_his_role(api_client):
    user = UserFactory()
    first = OrganizationFactory(name="Alpha Médias")
    second = OrganizationFactory(name="Bêta Communication")
    MembershipFactory(organization=first, user=user, role=OWNER)
    MembershipFactory(organization=second, user=user, role=MEMBER)
    MembershipFactory(organization=OrganizationFactory(name="Pas la mienne"))
    _authenticate(api_client, user)

    response = api_client.get("/api/organizations/")

    assert response.status_code == 200
    assert [(o["name"], o["my_role"]) for o in response.data] == [
        ("Alpha Médias", OWNER),
        ("Bêta Communication", MEMBER),
    ]
    assert response.data[0]["id"] == str(first.id)


@pytest.mark.django_db
def test_multi_organization_user_gets_a_clear_message_and_a_code_without_header(api_client):
    user = UserFactory()
    MembershipFactory(organization=OrganizationFactory(), user=user)
    MembershipFactory(organization=OrganizationFactory(), user=user)
    _authenticate(api_client, user)

    response = api_client.get("/api/jobs/")

    assert response.status_code == 403
    assert response.data["code"] == "organization_required"
    assert "plusieurs organisations" in response.data["detail"]
    assert "X-Organization-Id" not in response.data["detail"]


@pytest.mark.django_db
def test_accepting_a_second_organization_then_switching_with_the_header(api_client):
    """Essai perso puis invitation de l'employeur : le compte rejoint la 2e organisation et
    choisit ensuite celle avec laquelle travailler."""
    user = UserFactory(email="awa@presse.cm")
    personal = OrganizationFactory(name="Perso")
    MembershipFactory(organization=personal, user=user, role=OWNER)
    employer = OrganizationFactory(name="Employeur")
    boss = UserFactory()
    MembershipFactory(organization=employer, user=boss, role=OWNER)
    invitation = create_invitation(organization=employer, email="awa@presse.cm", role=MEMBER, invited_by=boss)
    PressReviewJob.objects.create(organization=employer, title="Revue de l'employeur")
    _authenticate(api_client, user)

    accepted = api_client.post(f"/api/auth/invitations/{invitation.token}/accept/")
    assert accepted.status_code == 200, accepted.data
    assert accepted.data["organization"] == str(employer.id)
    response = api_client.get("/api/jobs/", HTTP_X_ORGANIZATION_ID=str(employer.id))

    assert response.status_code == 200
    assert [job["title"] for job in response.data["results"]] == ["Revue de l'employeur"]
    me = api_client.get("/api/organizations/me/", HTTP_X_ORGANIZATION_ID=str(employer.id))
    assert me.data["name"] == "Employeur"
    assert me.data["my_role"] == MEMBER


@pytest.mark.django_db
@pytest.mark.parametrize("header", ["00000000-0000-0000-0000-000000000000", "pas-un-uuid"])
def test_removed_member_or_bad_header_gets_organization_access_lost(api_client, team, header):
    removed_org_id = str(team["org"].id)
    team["member_m"].delete()
    _authenticate(api_client, team["member"])

    for value in (removed_org_id, header):
        response = api_client.get("/api/jobs/", HTTP_X_ORGANIZATION_ID=value)
        assert response.status_code == 403
        assert response.data["code"] == "organization_access_lost"
        assert response.data["detail"] == "Vous n'avez plus accès à cette organisation."
