from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Pas de service public de /media/ (même en DEBUG) : les fichiers clients ne sont
# accessibles que par lien signé (/api/media/…, cf. apps.core.media).
urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.press_review.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    # Réservés au staff hors dev (SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"]).
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
