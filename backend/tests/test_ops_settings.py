"""Choix du module de settings, garde-fous de production et Sentry facultatif."""
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from config import bootstrap
from config.sentry import init_sentry, read_revision
from config.settings_guard import is_local_host, public_hosts

BACKEND_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- DJANGO_SETTINGS_MODULE


def test_env_file_value_is_read_without_loading_anything_else(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# commentaire\nDJANGO_SECRET_KEY=abc\nDJANGO_SETTINGS_MODULE=config.settings.dev\n"
        "export DJANGO_SETTINGS_MODULE=\"config.settings.prod\"  # la dernière ligne gagne\n",
        encoding="utf-8",
    )

    assert bootstrap.settings_module_from_env_file(env_file) == "config.settings.prod"
    assert bootstrap.settings_module_from_env_file(tmp_path / "absent.env") is None


def test_environment_variable_wins_over_the_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.prod\n", encoding="utf-8")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.test")

    assert bootstrap.configure_settings_module(env_file) == "config.settings.test"


def test_env_file_is_used_when_the_variable_is_missing(tmp_path, monkeypatch, capsys):
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.prod\n", encoding="utf-8")
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE")

    assert bootstrap.configure_settings_module(env_file) == "config.settings.prod"
    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.prod"
    assert capsys.readouterr().err == ""


def test_falling_back_to_dev_is_never_silent(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE")

    assert bootstrap.configure_settings_module(tmp_path / "absent.env") == "config.settings.dev"
    assert "config.settings.prod" in capsys.readouterr().err


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "backend", "192.168.1.20", "[::1]", "app.localhost", "*", ".local"])
def test_development_hosts_are_local(host):
    assert is_local_host(host)


def test_a_real_domain_is_public():
    assert public_hosts(["localhost", "presse.mirlab.cloud", ".mirlab.cloud"]) == ["presse.mirlab.cloud", ".mirlab.cloud"]


def _import_settings(module, **env):
    """Importe un module de settings dans un processus neuf (le code de niveau module
    s'exécute à l'import : impossible à rejouer proprement dans le processus de test)."""
    environment = {**os.environ, "DJANGO_SETTINGS_MODULE": module, **env}
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=BACKEND_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_dev_settings_refuse_to_serve_a_public_domain():
    result = _import_settings("config.settings.dev", DJANGO_ALLOWED_HOSTS="presse.mirlab.cloud")

    assert result.returncode != 0
    assert "config.settings.prod" in result.stderr


def test_dev_settings_still_work_locally():
    result = _import_settings("config.settings.dev", DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,backend")

    assert result.returncode == 0, result.stderr


def test_prod_settings_require_a_real_secret_key():
    missing = _import_settings("config.settings.prod", DJANGO_SECRET_KEY="", SENTRY_DSN="")
    default = _import_settings("config.settings.prod", DJANGO_SECRET_KEY="dev-insecure-key-change-me", SENTRY_DSN="")
    real = _import_settings("config.settings.prod", DJANGO_SECRET_KEY="x" * 50, SENTRY_DSN="")

    assert missing.returncode != 0 and "DJANGO_SECRET_KEY" in missing.stderr
    assert default.returncode != 0
    assert real.returncode == 0, real.stderr


# --------------------------------------------------------------------------- Sentry


def test_sentry_stays_off_without_dsn():
    assert init_sentry(dsn="") is False


def test_sentry_is_initialised_for_django_and_celery_without_personal_data(monkeypatch):
    calls = {}
    sdk = types.ModuleType("sentry_sdk")
    sdk.init = lambda **kwargs: calls.update(kwargs)
    integrations = types.ModuleType("sentry_sdk.integrations")
    celery_module = types.ModuleType("sentry_sdk.integrations.celery")
    celery_module.CeleryIntegration = type("CeleryIntegration", (), {})
    django_module = types.ModuleType("sentry_sdk.integrations.django")
    django_module.DjangoIntegration = type("DjangoIntegration", (), {})
    for name, module in {
        "sentry_sdk": sdk,
        "sentry_sdk.integrations": integrations,
        "sentry_sdk.integrations.celery": celery_module,
        "sentry_sdk.integrations.django": django_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    assert init_sentry(dsn="https://cle@sentry.exemple/1", release="abc123") is True
    assert calls["send_default_pii"] is False
    assert calls["release"] == "abc123"
    assert {type(i).__name__ for i in calls["integrations"]} == {"CeleryIntegration", "DjangoIntegration"}


def test_missing_sentry_package_does_not_prevent_startup(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)  # import -> ImportError

    assert init_sentry(dsn="https://cle@sentry.exemple/1") is False
    assert "sentry-sdk" in capsys.readouterr().err


def test_release_is_read_from_the_revision_file_written_by_the_deploy(tmp_path):
    assert read_revision(tmp_path) == ""
    (tmp_path / "REVISION").write_text("4f2a9c1\n", encoding="utf-8")

    assert read_revision(tmp_path) == "4f2a9c1"
