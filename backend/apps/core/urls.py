from django.urls import path

from .media import serve_signed_media
from .views import HealthCheckView

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    # Fichiers clients (documents, exports, justificatifs) : liens signés, cf. apps.core.media.
    path("media/<int:expires>/<str:signature>/<path:path>", serve_signed_media, name="media-signed"),
]
