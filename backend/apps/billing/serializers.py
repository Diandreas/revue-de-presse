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

    class Meta:
        model = Subscription
        fields = [
            "id", "plan", "provider", "status",
            "current_period_start", "current_period_end", "cancel_at_period_end",
        ]
        read_only_fields = fields


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
