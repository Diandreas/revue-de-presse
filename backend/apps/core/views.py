from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .health import run_checks


class HealthCheckView(APIView):
    """Endpoint public de supervision (moniteur d'uptime externe, script de déploiement) :
    200 si tout répond, 503 sinon (détail par composant dans `checks`)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    # Sonde appelée en boucle par la supervision : jamais limitée (pas de fausse alerte).
    throttle_classes = []

    def get(self, request):
        report = run_checks()
        return Response(report, status=200 if report["status"] == "ok" else 503)
