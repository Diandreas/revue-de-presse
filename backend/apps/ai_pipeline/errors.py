"""Classification des erreurs du pipeline exécuté en arrière-plan.

Trois besoins distincts :
- `is_retryable_error` : une erreur *transitoire* (rate limit, indisponibilité du service,
  timeout réseau) ne doit pas faire échouer la revue — la tâche est relancée plus tard
  par Celery, sans intervention de l'utilisateur.
- `is_configuration_error` : un problème de *configuration du serveur* (moteur OCR absent,
  clé API refusée, modèle fermé à l'offre) n'est ni transitoire ni la faute d'un fichier :
  il doit faire échouer le job avec un message d'administrateur, jamais être imputé à un
  document précis.
- `describe_error` : un traitement en arrière-plan n'a personne devant les logs ; le
  message stocké sur le job (affiché dans l'interface) doit être lisible par un client,
  pas un corps JSON brut de l'API Mistral.
"""
import re

from pydantic import ValidationError


class OcrUnavailableError(Exception):
    """Le moteur de lecture (Tesseract, Poppler, ou le service Mistral utilisé pour lire les
    photos) est absent ou mal configuré sur le SERVEUR. Ce n'est pas un problème du fichier
    de l'utilisateur : il ne faut ni l'avaler (texte vide silencieux) ni le présenter comme
    « aucun texte lisible » — le job doit échouer franchement avec un message d'administrateur.

    `user_message` : message dédié à l'interface (sinon un message générique est utilisé)."""

    def __init__(self, message, *, user_message=None):
        super().__init__(message)
        self.user_message = user_message


RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})

_STATUS_IN_MESSAGE = re.compile(r"\bStatus (\d{3})\b")


def status_code_of(exc):
    """Code HTTP porté par l'exception (SDK Mistral, httpx...), ou None.

    Le SDK Mistral expose `status_code` ; à défaut (exception rewrappée, message seul),
    on le relit dans le texte (« ... Status 429 ... »)."""
    for attr in ("status_code", "raw_status_code", "http_status"):
        code = getattr(exc, attr, None)
        if isinstance(code, int):
            return code
    text = str(exc)
    match = _STATUS_IN_MESSAGE.search(text)
    if match:
        return int(match.group(1))
    if "rate_limited" in text:
        return 429
    return None


def is_quota_blocked(exc):
    """429 dont le quota est de **0** : Mistral répond « rate limit » (et non 403) quand le
    modèle n'est pas ouvert à l'offre du compte. Ce n'est pas un pic passager — attendre et
    réessayer ne servira jamais à rien (`x-ratelimit-limit-req-minute: 0`)."""
    if status_code_of(exc) != 429:
        return False
    headers = getattr(exc, "headers", None)
    if not headers:
        return False
    try:
        items = list(headers.items())
    except Exception:  # noqa: BLE001 - en-têtes de type inattendu : on ne présume de rien
        return False
    return any(str(k).lower().startswith("x-ratelimit-limit") and str(v).strip() == "0" for k, v in items)


def _is_network_error(exc):
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx est une dépendance de mistralai
        return False
    return isinstance(exc, httpx.TransportError)


def is_retryable_error(exc):
    if is_quota_blocked(exc):
        return False
    code = status_code_of(exc)
    if code is not None:
        return code in RETRYABLE_STATUS_CODES
    return _is_network_error(exc)


def is_configuration_error(exc):
    """Problème de configuration du serveur (à signaler à l'administrateur), pas d'un fichier."""
    return isinstance(exc, OcrUnavailableError) or is_quota_blocked(exc) or status_code_of(exc) in (401, 403)


def describe_error(exc, *, retried=False):
    """Message en français, sans jargon technique, pour l'affichage utilisateur.
    `retried` : des relances automatiques ont déjà eu lieu (et ont échoué)."""
    if isinstance(exc, OcrUnavailableError):
        return exc.user_message or (
            "Le moteur de lecture des photos et PDF scannés (OCR) n'est pas disponible sur le "
            "serveur. Ce n'est pas un problème de vos fichiers : contactez l'administrateur "
            "de la plateforme."
        )
    if isinstance(exc, ValidationError):
        return (
            "La réponse de l'IA n'a pas pu être interprétée (format inattendu). Réessayez ; si "
            "le problème persiste, contactez l'administrateur (modèle d'IA à changer)."
        )
    code = status_code_of(exc)
    text = str(exc)
    if type(exc).__name__ == "SoftTimeLimitExceeded":
        return "L'analyse a dépassé le temps maximum autorisé. Réessayez avec moins de fichiers."
    if is_quota_blocked(exc):
        return (
            "Le modèle d'IA configuré n'est pas accessible avec l'offre Mistral du compte "
            "(quota de 0 requête par minute). Contactez l'administrateur : il doit choisir un "
            "autre modèle (variables MISTRAL_MODEL / MISTRAL_VISION_MODEL) ou changer d'offre."
        )
    if code == 429:
        tried = "L'analyse a été relancée automatiquement sans succès. " if retried else ""
        return f"Limite de débit du service d'IA atteinte. {tried}Réessayez dans quelques minutes."
    if code == 403 and "tier_not_allowed" in text:
        return (
            "Le modèle d'IA configuré n'est pas autorisé par votre offre Mistral. "
            "Choisissez un modèle disponible (variable MISTRAL_MODEL) ou changez d'offre."
        )
    if code in (401, 403):
        return "La clé d'API du service d'IA est invalide ou n'a pas les droits nécessaires."
    if code is not None and code >= 500:
        return "Le service d'IA est momentanément indisponible. Réessayez dans quelques minutes."
    if _is_network_error(exc):
        return "Le service d'IA est injoignable (problème réseau). Réessayez dans quelques minutes."
    return text or type(exc).__name__
