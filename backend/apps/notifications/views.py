from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import NotificationPreference
from .serializers import NotificationPreferenceSerializer


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/notifications/preferences/ : préférences e-mail de l'utilisateur
    connecté (jamais celles d'un autre : aucun identifiant dans l'URL)."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        preference, _created = NotificationPreference.objects.get_or_create(user=self.request.user)
        return preference
