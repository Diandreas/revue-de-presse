from rest_framework import serializers

from apps.core.uploads import PAYMENT_PROOF_TYPES, VerifiedFileField

from .models import BillingProfile, Invoice, Plan, Subscription


def _viewer_is_staff(context):
    request = (context or {}).get("request")
    user = getattr(request, "user", None)
    return bool(user is not None and user.is_authenticated and user.is_staff)

PROOF_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 Mo


class PlanSerializer(serializers.ModelSerializer):
    """Les prix ne sont jamais montrés aux clients (formules « sur devis ») : `price_amount`
    vaut null pour tout utilisateur qui n'est pas membre de l'équipe (is_staff)."""

    class Meta:
        model = Plan
        fields = [
            "id", "code", "name", "price_amount", "currency",
            "billing_interval", "max_reviews_per_month", "max_seats",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not _viewer_is_staff(self.context):
            data["price_amount"] = None
        return data


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_trial = serializers.SerializerMethodField()
    reviews_used = serializers.SerializerMethodField()
    # Quota de l'essai (TRIAL_MAX_REVIEWS) ou quota mensuel de la formule.
    reviews_limit = serializers.SerializerMethodField()
    # Formule demandée au paiement, appliquée seulement une fois le paiement confirmé.
    pending_plan_code = serializers.SerializerMethodField()
    # Mêmes règles que le serveur (délai de grâce compris) : l'interface n'a rien à recalculer.
    has_access = serializers.SerializerMethodField()
    access_until = serializers.SerializerMethodField()
    seats_used = serializers.SerializerMethodField()
    seats_limit = serializers.IntegerField(source="plan.max_seats", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "provider", "status",
            "current_period_start", "current_period_end", "cancel_at_period_end",
            "is_trial", "reviews_used", "reviews_limit", "pending_plan_code",
            "has_access", "access_until", "seats_used", "seats_limit",
        ]
        read_only_fields = fields

    def get_is_trial(self, obj):
        return obj.status == Subscription.Status.TRIALING

    def get_pending_plan_code(self, obj):
        return (obj.metadata or {}).get("pending_plan_code")

    def get_reviews_used(self, obj):
        from .services import SubscriptionService

        return SubscriptionService.reviews_used(obj)

    def get_reviews_limit(self, obj):
        from .services import SubscriptionService

        return SubscriptionService.reviews_limit(obj)

    def get_has_access(self, obj):
        from .services import SubscriptionService

        return SubscriptionService.grants_access(obj)

    def get_access_until(self, obj):
        from .services import SubscriptionService

        until = SubscriptionService.access_until(obj)
        return serializers.DateTimeField().to_representation(until) if until else None

    def get_seats_used(self, obj):
        from .services import seats_used

        return seats_used(obj.organization)


class InvoiceSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)

    class Meta:
        model = Invoice
        fields = [
            "id", "number", "provider", "plan_name", "months",
            "amount", "amount_ht", "vat_rate", "vat_amount", "currency", "status",
            "period_start", "period_end", "paid_at", "created_at",
        ]
        read_only_fields = fields


class BillingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingProfile
        fields = ["legal_name", "address", "niu", "rccm", "email", "phone", "updated_at"]
        read_only_fields = ["updated_at"]


class CheckoutStripeSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()


class CheckoutMobileMoneySerializer(serializers.Serializer):
    plan_code = serializers.SlugField()
    phone_number = serializers.CharField(max_length=20)


class CheckoutBankTransferSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()


class InvoiceProofUploadSerializer(serializers.Serializer):
    # Type réel vérifié dans les octets et extension imposée (cf. apps.core.uploads).
    proof = VerifiedFileField(
        allowed_types=PAYMENT_PROOF_TYPES,
        max_size=PROOF_MAX_SIZE_BYTES,
        formats_message="Justificatif accepté : PDF, JPG ou PNG.",
    )


class InvoiceReviewSerializer(serializers.Serializer):
    """`approve` lu comme un vrai booléen : « false » / 0 refusent (avant, toute valeur non
    vide — y compris la chaîne "false" — valait approbation)."""

    approve = serializers.BooleanField()
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
