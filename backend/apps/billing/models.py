from pathlib import PurePosixPath

from django.conf import settings
from django.db import models

from apps.accounts.models import Organization
from apps.core.models import TimeStampedModel

# cf. apps.press_review.models.FILE_PATH_MAX_LENGTH : évite un SuspiciousFileOperation
# quand le chemin (organizations/<uuid>/.../<uuid>...) dépasse le max_length=100 par
# défaut de Django.
FILE_PATH_MAX_LENGTH = 255


def invoice_proof_upload_path(instance, filename):
    suffix = PurePosixPath(filename).suffix[:10]
    return f"organizations/{instance.organization_id}/invoice_proofs/{instance.id}{suffix}"


class Plan(TimeStampedModel):
    class BillingInterval(models.TextChoices):
        MONTHLY = "monthly", "Mensuel"

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="XAF")
    billing_interval = models.CharField(
        max_length=20, choices=BillingInterval.choices, default=BillingInterval.MONTHLY
    )
    max_reviews_per_month = models.PositiveIntegerField()
    max_seats = models.PositiveIntegerField()
    stripe_price_id = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price_amount"]

    def __str__(self):
        return self.name


class Subscription(TimeStampedModel):
    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe (carte)"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        BANK_TRANSFER = "bank_transfer", "Virement bancaire"

    class Status(models.TextChoices):
        TRIALING = "trialing", "Essai"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "En retard"
        CANCELED = "canceled", "Annulée"
        INCOMPLETE = "incomplete", "Incomplète"

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    provider_customer_id = models.CharField(max_length=255, blank=True)
    provider_subscription_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INCOMPLETE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.organization} · {self.plan} ({self.status})"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PENDING_REVIEW = "pending_review", "Justificatif à valider"
        PAID = "paid", "Payée"
        FAILED = "failed", "Échouée"
        REFUNDED = "refunded", "Remboursée"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invoices")
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="invoices")
    provider = models.CharField(max_length=20, choices=Subscription.Provider.choices)
    provider_reference = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="XAF")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    proof_file = models.FileField(
        upload_to=invoice_proof_upload_path, null=True, blank=True, max_length=FILE_PATH_MAX_LENGTH
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Facture {self.id} · {self.organization} ({self.status})"
