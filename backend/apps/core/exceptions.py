from rest_framework.views import exception_handler as drf_exception_handler


def api_exception_handler(exc, context):
    """Enveloppe uniforme des erreurs API : garantit toujours une clé `detail`
    exploitable par le frontend, même pour les erreurs de validation par champ
    (qui restent en plus disponibles telles quelles pour l'affichage par champ)."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

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
