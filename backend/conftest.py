import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membership, Organization, User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="owner@example.com", password="testpass1234", full_name="Owner Test")


@pytest.fixture
def organization(db, user):
    org = Organization.objects.create(name="Organisation Test", created_by=user)
    Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)
    return org


@pytest.fixture
def authenticated_client(api_client, user, organization):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return api_client
