"""Limitation de débit de l'API (force brute sur les mots de passe, création d'essais à la
chaîne, saturation du disque ou du quota Mistral).

Les compteurs vivent dans le cache Django (Redis en production, cf. CACHES) et les taux
dans REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]. Trois niveaux, tous actifs par défaut
(DEFAULT_THROTTLE_CLASSES) :

- global, par IP pour les visiteurs anonymes (« anon ») et par utilisateur (« user ») ;
- par route sensible (connexion, inscription, invitations, dépôts, lancement de revues…) :
  portée lue dans `view.throttle_scope` si la vue la déclare, sinon dans ROUTE_SCOPES ;
- par adresse e-mail saisie, pour toute portée « X » qui a un taux « X_email » (connexion,
  mot de passe oublié) : changer d'IP ne permet pas de s'acharner sur un même compte.

Une panne du cache (Redis arrêté) ne doit pas bloquer l'appli : la requête passe alors
sans limite et l'incident est journalisé.
"""
import hashlib
import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework import throttling
from rest_framework.settings import api_settings

logger = logging.getLogger(__name__)

# Nom de route (cf. urls.py des apps) -> {méthode HTTP: portée}. Une vue peut aussi
# déclarer `throttle_scope = "..."` (ex. réinitialisation du mot de passe : « password_reset »).
ROUTE_SCOPES = {
    "auth-token": {"POST": "login"},
    "auth-register": {"POST": "register"},
    "auth-invitation-detail": {"GET": "invitations"},
    "auth-invitation-accept": {"POST": "invitations"},
    "auth-invitation-register": {"POST": "invitations"},
    "organization-invite": {"POST": "invitations"},
    "document-list-create": {"POST": "uploads"},
    "billing-invoice-proof": {"POST": "uploads"},
    "job-list-create": {"POST": "jobs"},
    "job-retry": {"POST": "jobs"},
}


def route_scope(request, view):
    """Portée de limitation applicable à cette requête, ou None."""
    scope = getattr(view, "throttle_scope", None)
    if scope:
        return scope
    match = getattr(request, "resolver_match", None)
    if match is None:
        return None
    return ROUTE_SCOPES.get(match.url_name, {}).get(request.method)


class ResilientRateMixin:
    """Taux relus à chaque requête (surchargeables dans les tests, contrairement à
    l'attribut de classe THROTTLE_RATES de DRF) et tolérance aux pannes du cache."""

    def get_rate(self):
        try:
            return api_settings.DEFAULT_THROTTLE_RATES[self.scope]
        except KeyError as exc:
            raise ImproperlyConfigured(f"Aucun taux de limitation défini pour la portée « {self.scope} ».") from exc

    def use_scope(self, scope):
        self.scope = scope
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

    def allow_request(self, request, view):
        return self.check_history(request, view)

    def check_history(self, request, view):
        """Historique des requêtes dans le cache (SimpleRateThrottle de DRF)."""
        try:
            return throttling.SimpleRateThrottle.allow_request(self, request, view)
        except ImproperlyConfigured:
            raise
        except Exception:  # noqa: BLE001 - Redis injoignable, délai dépassé…
            logger.warning("Limitation de débit ignorée (cache indisponible).", exc_info=True)
            return True


class AnonRateThrottle(ResilientRateMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(ResilientRateMixin, throttling.UserRateThrottle):
    pass


class RouteScopedRateThrottle(ResilientRateMixin, throttling.ScopedRateThrottle):
    """ScopedRateThrottle de DRF (par utilisateur, ou par IP pour un visiteur), dont la
    portée peut aussi venir de ROUTE_SCOPES — elle ne vise alors que la méthode indiquée :
    lister ses documents ne consomme pas le quota de dépôts."""

    def allow_request(self, request, view):
        scope = route_scope(request, view)
        if not scope:
            return True
        self.use_scope(scope)
        return self.check_history(request, view)


class EmailRateThrottle(ResilientRateMixin, throttling.SimpleRateThrottle):
    """Limite par adresse e-mail (champ « email » du corps) pour les portées qui ont un taux
    « <portée>_email » : « login_email » pour la connexion, « password_reset_email » pour
    le mot de passe oublié."""

    def __init__(self):
        # Portée et taux dépendent de la route : ils ne sont connus qu'à l'appel.
        pass

    def allow_request(self, request, view):
        base_scope = route_scope(request, view)
        scope = f"{base_scope}_email" if base_scope else None
        if not scope or scope not in api_settings.DEFAULT_THROTTLE_RATES:
            return True
        self.use_scope(scope)
        return self.check_history(request, view)

    def get_cache_key(self, request, view):
        try:
            email = request.data.get("email")
        except Exception:  # noqa: BLE001 - corps illisible : la vue répondra 400
            return None
        if not isinstance(email, str) or not email.strip():
            return None
        digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class AdminLoginRateThrottle(ResilientRateMixin, throttling.SimpleRateThrottle):
    """Tentatives de connexion à l'admin Django, par IP (cf. AdminLoginThrottleMiddleware)."""

    scope = "admin_login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class AdminLoginUsernameRateThrottle(AdminLoginRateThrottle):
    """Tentatives de connexion à l'admin Django, par identifiant saisi (compte staff visé)."""

    def get_cache_key(self, request, view):
        username = request.POST.get("username", "")
        if not username.strip():
            return None
        digest = hashlib.sha256(username.strip().lower().encode()).hexdigest()
        return self.cache_format % {"scope": f"{self.scope}_user", "ident": digest}
