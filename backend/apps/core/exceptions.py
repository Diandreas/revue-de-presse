import math

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler as drf_exception_handler


def throttled_message(wait):
    """« Trop de tentatives » + délai lisible (le Retry-After reste fourni par DRF)."""
    if not wait:
        return "Trop de tentatives. Réessayez dans quelques instants."
    seconds = math.ceil(wait)
    if seconds < 60:
        delay = f"{seconds} seconde{'s' if seconds > 1 else ''}"
    else:
        minutes = math.ceil(seconds / 60)
        delay = f"{minutes} minute{'s' if minutes > 1 else ''}"
    return f"Trop de tentatives. Réessayez dans {delay}."


def api_exception_handler(exc, context):
    """Enveloppe uniforme des erreurs API : garantit toujours une clé `detail`
    exploitable par le frontend, même pour les erreurs de validation par champ
    (qui restent en plus disponibles telles quelles pour l'affichage par champ)."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, Throttled):
        response.data = {"detail": throttled_message(exc.wait)}
        return response

    data = response.data
    if isinstance(data, list):
        # `raise ValidationError("message")` produit une liste à un seul élément côté
        # DRF (contrairement à PermissionDenied/NotFound) : on la déplie pour que le
        # message explicite reste dans `detail`, exploité tel quel par le frontend.
        if len(data) == 1 and isinstance(data[0], str):
            response.data = {"detail": str(data[0])}
        else:
            response.data = {"detail": "Une erreur est survenue.", "errors": data}
    elif isinstance(data, dict) and "detail" not in data:
        response.data = {"detail": "Une erreur de validation est survenue.", "errors": data}
    return response
