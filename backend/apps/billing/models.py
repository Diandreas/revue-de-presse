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
    price_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Prix catalogue HT par mois. Jamais affiché aux clients (formules « sur devis ») : "
        "sert de base aux factures et de montant proposé lors d'un paiement manuel.",
    )
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
        MANUAL = "manual", "Paiement manuel (équipe)"

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

    class Meta:
        verbose_name = "abonnement"
        verbose_name_plural = "abonnements"

    def __str__(self):
        return f"{self.organization} · {self.plan} ({self.status})"


class BillingProfile(TimeStampedModel):
    """Identité légale de l'entreprise cliente, reportée sur ses factures (raison sociale,
    NIU, RCCM). Renseignée par le client (page Abonnement) ou par l'équipe (admin)."""

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name="billing_profile")
    legal_name = models.CharField("raison sociale", max_length=255, blank=True)
    address = models.TextField("adresse", blank=True)
    niu = models.CharField("NIU", max_length=50, blank=True, help_text="Numéro d'identifiant unique (fiscal).")
    rccm = models.CharField("RCCM", max_length=60, blank=True)
    email = models.EmailField("e-mail de facturation", blank=True)
    phone = models.CharField("téléphone", max_length=30, blank=True)

    class Meta:
        verbose_name = "informations de facturation"
        verbose_name_plural = "informations de facturation"

    def __str__(self):
        return self.legal_name or str(self.organization)


class InvoiceCounter(models.Model):
    """Dernier numéro de facture attribué pour une année (numérotation sans trou)."""

    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year} : {self.last_number}"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PENDING_REVIEW = "pending_review", "Justificatif à valider"
        PAID = "paid", "Payée"
        FAILED = "failed", "Échouée"
        REFUNDED = "refunded", "Remboursée"

    # Une facture est une pièce comptable : elle survit à la suppression de l'organisation
    # (le nom de l'acheteur est figé dans `buyer_name` / `buyer`).
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    # Formule payée par cette facture, appliquée à l'abonnement quand elle est réglée.
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, null=True, blank=True, related_name="invoices")
    number = models.CharField("numéro", max_length=32, unique=True, null=True, blank=True, editable=False)
    months = models.PositiveSmallIntegerField("mois couverts", default=1)
    provider = models.CharField(max_length=20, choices=Subscription.Provider.choices)
    provider_reference = models.CharField("référence du paiement", max_length=255, blank=True)
    amount = models.DecimalField("montant TTC", max_digits=12, decimal_places=2)
    amount_ht = models.DecimalField("montant HT", max_digits=12, decimal_places=2, null=True, blank=True)
    vat_rate = models.DecimalField("taux de TVA (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    vat_amount = models.DecimalField("montant de TVA", max_digits=12, decimal_places=2, null=True, blank=True)
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
    buyer_name = models.CharField("client", max_length=255, blank=True)
    seller = models.JSONField("vendeur (figé)", default=dict, blank=True)
    buyer = models.JSONField("client (figé)", default=dict, blank=True)
    notes = models.TextField("notes internes", blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "facture"
        verbose_name_plural = "factures"

    def save(self, *args, **kwargs):
        # Numéro, identités et ventilation HT/TVA sont fixés à la création (jamais sur une
        # sauvegarde partielle : un numéro tiré sans être enregistré créerait un trou).
        if kwargs.get("update_fields") is None:
            from .invoicing import prepare_invoice

            prepare_invoice(self)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Facture {self.number or self.id} · {self.buyer_name or self.organization} ({self.status})"
