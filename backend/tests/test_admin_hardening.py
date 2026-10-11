"""Administration et réglages de production : admin sur un chemin configurable et freinée
contre la force brute, documentation de l'API réservée au staff, clé secrète exigée."""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.management.utils import get_random_secret_key
from django.test import Client
from django.urls import clear_url_caches
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.checks import check_security_settings
from tests.factories import UserFactory

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def rates(settings):
    def _set(**overrides):
        current = settings.REST_FRAMEWORK
        settings.REST_FRAMEWORK = {
            **current,
            "DEFAULT_THROTTLE_RATES": {**current["DEFAULT_THROTTLE_RATES"], **overrides},
        }

    return _set


# --------------------------------------------------------------------------- admin


@pytest.mark.django_db
def test_admin_login_is_throttled_per_ip(rates):
    rates(admin_login="2/min")
    client = Client(REMOTE_ADDR="10.0.0.1")

    statuses = [
        client.post("/admin/login/", {"username": f"staff{i}@example.com", "password": "x"}).status_code
        for i in range(3)
    ]

    assert statuses == [200, 200, 429]  # 200 = formulaire réaffiché avec l'erreur
    assert Client(REMOTE_ADDR="10.0.0.2").post("/admin/login/", {"username": "a", "password": "x"}).status_code == 200


@pytest.mark.django_db
def test_admin_login_is_throttled_per_username(rates):
    rates(admin_login="2/min")

    statuses = [
        Client(REMOTE_ADDR=f"10.0.0.{i}").post("/admin/login/", {"username": "staff@example.com", "password": "x"})
        for i in range(3)
    ]

    assert [r.status_code for r in statuses] == [200, 200, 429]
    assert "Trop de tentatives" in statuses[-1].content.decode()
    assert int(statuses[-1]["Retry-After"]) > 0


@pytest.mark.django_db
def test_admin_login_page_itself_is_not_throttled(rates):
    rates(admin_login="1/min")
    client = Client()

    assert [client.get("/admin/login/").status_code for _ in range(3)] == [200, 200, 200]


@pytest.mark.django_db
def test_admin_path_is_configurable(settings):
    import config.urls

    settings.ADMIN_URL = "gestion-7f3k9q/"
    try:
        importlib.reload(config.urls)
        clear_url_caches()
        assert Client().get("/gestion-7f3k9q/login/").status_code == 200
        assert Client().get("/admin/login/").status_code == 404
    finally:
        settings.ADMIN_URL = "admin/"
        importlib.reload(config.urls)
        clear_url_caches()


# --------------------------------------------------------------------------- documentation de l'API


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/docs/", "/api/schema/"])
def test_api_docs_are_closed_to_the_public(url):
    assert Client().get(url).status_code in (401, 403)


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/docs/", "/api/schema/"])
def test_api_docs_are_closed_to_client_users(url):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(UserFactory()).access_token}")

    assert client.get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/api/docs/", "/api/schema/"])
def test_api_docs_are_open_to_staff_logged_into_the_admin(url):
    client = Client()
    client.force_login(UserFactory(is_staff=True))

    assert client.get(url).status_code == 200


# --------------------------------------------------------------------------- contrôles --deploy


def test_deploy_checks_flag_weak_security_settings(settings):
    settings.ADMIN_URL = "admin/"
    settings.MEDIA_X_ACCEL_REDIRECT = False
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": None}

    ids = {warning.id for warning in check_security_settings(None)}

    assert ids == {"core.W001", "core.W002", "core.W003", "core.W004"}


def test_deploy_checks_pass_with_production_settings(settings):
    settings.ADMIN_URL = "gestion-7f3k9q/"
    settings.MEDIA_X_ACCEL_REDIRECT = True
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": "redis://x"}}

    assert check_security_settings(None) == []


# --------------------------------------------------------------------------- réglages de production


def _load_production_settings(monkeypatch, **env):
    """Importe config.settings.prod avec cet environnement (sans toucher aux réglages actifs)."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delitem(sys.modules, "config.settings.prod", raising=False)
    return importlib.import_module("config.settings.prod")


def test_production_process_refuses_to_start_without_a_secret_key():
    environment = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod", "DJANGO_SECRET_KEY": ""}
    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND_DIR, env=environment, capture_output=True, text=True, timeout=120,
    )

    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert "DJANGO_SECRET_KEY" in result.stderr


@pytest.mark.parametrize(
    "secret_key",
    ["dev-insecure-key-change-me", "test-secret-key", "django-insecure-" + "a1b2c3" * 10, "court-mais-varie-123", "x" * 64],
)
def test_production_refuses_public_or_weak_secret_keys(monkeypatch, secret_key):
    from django.core.exceptions import ImproperlyConfigured

    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        _load_production_settings(monkeypatch, DJANGO_SECRET_KEY=secret_key)


def test_production_starts_with_a_strong_key_and_debug_forced_off(monkeypatch):
    monkeypatch.delenv("MEDIA_X_ACCEL_REDIRECT", raising=False)
    monkeypatch.delenv("DJANGO_NUM_PROXIES", raising=False)
    monkeypatch.delenv("DJANGO_SECURE_HSTS_SECONDS", raising=False)

    prod = _load_production_settings(monkeypatch, DJANGO_SECRET_KEY=get_random_secret_key(), DJANGO_DEBUG="True")

    assert prod.DEBUG is False
    assert prod.MEDIA_X_ACCEL_REDIRECT is True
    assert prod.REST_FRAMEWORK["NUM_PROXIES"] == 1
    assert prod.SECURE_HSTS_SECONDS == 365 * 24 * 3600
