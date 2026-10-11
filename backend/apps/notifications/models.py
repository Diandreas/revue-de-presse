from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class NotificationPreference(TimeStampedModel):
    """Choix de l'utilisateur sur les e-mails qui le concernent personnellement. Les
    e-mails liés au compte (fin d'essai, invitation…) ne sont pas désactivables."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preference"
    )
    email_review_updates = models.BooleanField(
        default=True, help_text="E-mail quand une revue lancée par l'utilisateur est prête ou a échoué."
    )

    class Meta:
        verbose_name = "Préférence de notification"
        verbose_name_plural = "Préférences de notification"

    def __str__(self):
        return f"Préférences de {self.user}"

    @classmethod
    def wants_review_updates(cls, user):
        preference = cls.objects.filter(user=user).only("email_review_updates").first()
        return preference is None or preference.email_review_updates


class NotificationLog(TimeStampedModel):
    """Trace des envois planifiés déjà faits : un rappel (fin d'essai, récapitulatif du
    staff) part une seule fois même si la tâche tourne plusieurs fois ou est rejouée."""

    kind = models.CharField(max_length=50)
    key = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Notification envoyée"
        verbose_name_plural = "Notifications envoyées"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "key"], name="unique_notification_per_kind_key"),
        ]

    def __str__(self):
        return f"{self.kind} · {self.key}"

    @classmethod
    def claim(cls, kind, key):
        """True si cet envoi n'a encore jamais été fait (et le réserve)."""
        _log, created = cls.objects.get_or_create(kind=kind, key=key)
        return created
