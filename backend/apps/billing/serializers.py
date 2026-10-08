from rest_framework import serializers

from .models import Invoice, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id", "code", "name", "price_amount", "currency",
            "billing_interval", "max_reviews_per_month", "max_seats",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_trial = serializers.SerializerMethodField()
    reviews_used = serializers.SerializerMethodField()
    reviews_limit = serializers.IntegerField(source="plan.max_reviews_per_month", read_only=True)
    # Formule demandée au paiement, appliquée seulement une fois le paiement confirmé.
    pending_plan_code = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "provider", "status",
            "current_period_start", "current_period_end", "cancel_at_period_end",
            "is_trial", "reviews_used", "reviews_limit", "pending_plan_code",
        ]
        read_only_fields = fields

    def get_is_trial(self, obj):
        return obj.status == Subscription.Status.TRIALING

    def get_pending_plan_code(self, obj):
        return (obj.metadata or {}).get("pending_plan_code")

    def get_reviews_used(self, obj):
        from .services import SubscriptionService

        return SubscriptionService.reviews_used(obj)


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            "id", "provider", "amount", "currency", "status",
            "period_start", "period_end", "paid_at", "proof_file", "created_at",
        ]
        read_only_fields = fields


class CheckoutStripeSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()


class CheckoutMobileMoneySerializer(serializers.Serializer):
    plan_code = serializers.SlugField()
    phone_number = serializers.CharField(max_length=20)


class CheckoutBankTransferSerializer(serializers.Serializer):
    plan_code = serializers.SlugField()


class InvoiceProofUploadSerializer(serializers.Serializer):
    proof = serializers.FileField()
