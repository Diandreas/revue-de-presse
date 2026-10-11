"""Garde-fou : les settings de développement (DEBUG=True, pages d'erreur détaillées) ne
doivent jamais servir un vrai nom de domaine. Si config.settings.dev est chargé avec
DJANGO_ALLOWED_HOSTS=presse.mirlab.cloud, c'est que DJANGO_SETTINGS_MODULE a été oublié :
on refuse de démarrer plutôt que d'exposer des traces d'erreur en production."""
import ipaddress

# Suffixes réservés au réseau local / aux tests (RFC 6761, mDNS, usages courants).
LOCAL_SUFFIXES = (".localhost", ".local", ".test", ".internal", ".lan", ".home.arpa")
LOCAL_NAMES = {"localhost", "backend", "testserver", "*", "0.0.0.0", "[::1]", "::1"}


def is_local_host(host):
    """Nom d'hôte de développement : localhost, nom de service Docker (sans point),
    adresse IP (y compris IP du réseau local pour tester sur téléphone)."""
    name = host.strip().lower().lstrip(".")
    if not name or name in LOCAL_NAMES or "." not in name:
        return True
    try:
        ipaddress.ip_address(name.strip("[]"))
        return True
    except ValueError:
        pass
    return name.endswith(LOCAL_SUFFIXES)


def public_hosts(hosts):
    return [host for host in hosts if not is_local_host(host)]
