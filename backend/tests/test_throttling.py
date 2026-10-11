"""Limitation de débit : force brute sur la connexion, essais créés à la chaîne, dépôts et
lancements de revues en rafale. Les taux sont abaissés test par test."""
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import throttled_message
from tests.image_fixtures import make_image_bytes

LOGIN_URL = "/api/auth/token/"


@pytest.fixture
def rates(settings):
    """rates(login="2/min", ...) : abaisse les taux de limitation pour ce test."""

    def _set(**overrides):
        current = settings.REST_FRAMEWORK
        settings.REST_FRAMEWORK = {
            **current,
            "DEFAULT_THROTTLE_RATES": {**current["DEFAULT_THROTTLE_RATES"], **overrides},
        }

    return _set


def _login(client, email, password="mauvais-mot-de-passe"):
    return client.post(LOGIN_URL, {"email": email, "password": password}, format="json")


# --------------------------------------------------------------------------- connexion


@pytest.mark.django_db
def test_login_is_limited_per_ip(rates):
    rates(login="3/min", login_email="100/min")
    client = APIClient(REMOTE_ADDR="10.0.0.1")

    statuses = [_login(client, f"victime{i}@example.com").status_code for i in range(3)]
    blocked = _login(client, "victime9@example.com")

    assert statuses == [401, 401, 401]
    assert blocked.status_code == 429
    assert blocked.data["detail"].startswith("Trop de tentatives. Réessayez dans ")
    assert int(blocked["Retry-After"]) > 0
    # Une autre IP n'est pas pénalisée.
    assert _login(APIClient(REMOTE_ADDR="10.0.0.2"), "victime9@example.com").status_code == 401


@pytest.mark.django_db
def test_login_is_limited_per_email_whatever_the_ip(rates, user):
    rates(login="100/min", login_email="2/min")

    assert _login(APIClient(REMOTE_ADDR="10.0.0.1"), "owner@example.com").status_code == 401
    assert _login(APIClient(REMOTE_ADDR="10.0.0.2"), "Owner@Example.com").status_code == 401
    # Même le bon mot de passe attend : le compte est visé par une rafale.
    blocked = _login(APIClient(REMOTE_ADDR="10.0.0.3"), " OWNER@example.com", password="testpass1234")
    assert blocked.status_code == 429
    assert _login(APIClient(REMOTE_ADDR="10.0.0.4"), "autre@example.com").status_code == 401


@pytest.mark.django_db
def test_successful_login_still_works_under_the_limit(user):
    response = _login(APIClient(), "owner@example.com", password="testpass1234")

    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_client_ip_comes_from_the_trusted_proxy_not_from_a_forged_header(rates, settings):
    rates(login="2/min", login_email="100/min")
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    client = APIClient(REMOTE_ADDR="127.0.0.1")  # nginx

    # Le client ajoute de fausses IP devant la sienne (1.2.3.4, ajoutée par nginx).
    first = client.post(LOGIN_URL, {"email": "a@example.com", "password": "x"}, HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4")
    second = client.post(LOGIN_URL, {"email": "b@example.com", "password": "x"}, HTTP_X_FORWARDED_FOR="7.7.7.7, 1.2.3.4")
    third = client.post(LOGIN_URL, {"email": "c@example.com", "password": "x"}, HTTP_X_FORWARDED_FOR="8.8.8.8, 1.2.3.4")
    other_client = client.post(LOGIN_URL, {"email": "d@example.com", "password": "x"}, HTTP_X_FORWARDED_FOR="1.2.3.5")

    assert [first.status_code, second.status_code, third.status_code] == [401, 401, 429]
    assert other_client.status_code == 401


# --------------------------------------------------------------------------- inscription, invitations


@pytest.mark.django_db
def test_registration_is_limited_per_ip(rates):
    rates(register="2/hour")
    client = APIClient()

    statuses = [client.post("/api/auth/register/", {}, format="json").status_code for _ in range(3)]

    assert statuses == [400, 400, 429]


@pytest.mark.django_db
def test_public_invitation_endpoints_are_limited(rates):
    rates(invitations="2/hour")
    client = APIClient()

    statuses = [client.get(f"/api/auth/invitations/jeton-{i}/").status_code for i in range(3)]

    assert statuses == [404, 404, 429]


# --------------------------------------------------------------------------- dépôts, revues


def _png():
    return SimpleUploadedFile("coupure.png", make_image_bytes(), content_type="image/png")


@pytest.mark.django_db
def test_uploads_are_limited_but_listing_is_not(rates, authenticated_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    rates(uploads="2/hour")

    statuses = [
        authenticated_client.post("/api/documents/", {"file": _png()}, format="multipart").status_code for _ in range(3)
    ]

    assert statuses == [201, 201, 429]
    assert authenticated_client.get("/api/documents/").status_code == 200


@pytest.mark.django_db
def test_job_creation_is_limited(rates, authenticated_client):
    rates(jobs="1/hour")

    first = authenticated_client.post("/api/jobs/", {"document_ids": []}, format="json")
    second = authenticated_client.post("/api/jobs/", {"document_ids": []}, format="json")

    assert first.status_code != 429
    assert second.status_code == 429
    assert authenticated_client.get("/api/jobs/").status_code == 200


# --------------------------------------------------------------------------- portée déclarée par une vue


class _PasswordResetLikeView(APIView):
    """Vue du futur « mot de passe oublié » (paquet comptes) : déclare sa portée."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "password_reset"

    def post(self, request):
        return Response(status=202)


def _reset(email, ip="10.0.0.1"):
    request = APIRequestFactory().post("/x/", {"email": email}, format="json", REMOTE_ADDR=ip)
    return _PasswordResetLikeView.as_view()(request)


def test_view_declaring_password_reset_scope_is_limited_by_default(rates):
    rates(password_reset="2/hour", password_reset_email="100/hour")

    statuses = [_reset(f"u{i}@example.com").status_code for i in range(3)]

    assert statuses == [202, 202, 429]


def test_password_reset_is_also_limited_per_email(rates):
    rates(password_reset="100/hour", password_reset_email="1/hour")

    assert _reset("cible@example.com", ip="10.0.0.1").status_code == 202
    assert _reset("CIBLE@example.com", ip="10.0.0.2").status_code == 429
    assert _reset("autre@example.com", ip="10.0.0.3").status_code == 202


def test_unknown_scope_is_a_configuration_error():
    class _Misconfigured(_PasswordResetLikeView):
        throttle_scope = "portee-inconnue"

    request = APIRequestFactory().post("/x/", {}, format="json")
    with pytest.raises(ImproperlyConfigured):
        _Misconfigured.as_view()(request)


# --------------------------------------------------------------------------- global, résilience


@pytest.mark.django_db
def test_anonymous_requests_are_limited_globally_but_not_the_health_probe(rates):
    rates(anon="2/min")
    client = APIClient()

    refresh = [client.post("/api/auth/token/refresh/").status_code for _ in range(3)]
    health = [client.get("/api/health/").status_code for _ in range(3)]

    assert refresh == [204, 204, 429]
    assert health == [200, 200, 200]


@pytest.mark.django_db
def test_authenticated_requests_are_limited_per_user(rates, authenticated_client):
    rates(user="2/min")

    statuses = [authenticated_client.get("/api/jobs/").status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


class _BrokenCache:
    def get(self, *args, **kwargs):
        raise ConnectionError("Redis injoignable")

    set = get


@pytest.mark.django_db
def test_cache_outage_does_not_block_logins(monkeypatch, user, caplog):
    monkeypatch.setattr(SimpleRateThrottle, "cache", _BrokenCache())

    with caplog.at_level("WARNING", logger="apps.core.throttling"):
        response = _login(APIClient(), "owner@example.com", password="testpass1234")

    assert response.status_code == 200
    assert "Limitation de débit ignorée (cache indisponible)." in caplog.messages


@pytest.mark.parametrize(
    ("wait", "message"),
    [
        (None, "Trop de tentatives. Réessayez dans quelques instants."),
        (0.4, "Trop de tentatives. Réessayez dans 1 seconde."),
        (42.1, "Trop de tentatives. Réessayez dans 43 secondes."),
        (61, "Trop de tentatives. Réessayez dans 2 minutes."),
    ],
)
def test_throttled_message_is_readable(wait, message):
    assert throttled_message(wait) == message
