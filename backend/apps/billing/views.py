import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsOrgAdmin, IsOrgMember, OrganizationContextMixin

from .models import Invoice, Plan, Subscription
from .providers import get_provider
from .providers.campay_provider import CamPayProvider
from .providers.stripe_provider import StripeProvider
from .serializers import (
    CheckoutBankTransferSerializer,
    CheckoutMobileMoneySerializer,
    CheckoutStripeSerializer,
    InvoiceProofUploadSerializer,
    InvoiceSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)
from .services import SubscriptionService

logger = logging.getLogger(__name__)


class PlanListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(is_active=True)


class SubscriptionMeView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request):
        subscription = getattr(request.organization, "subscription", None)
        if subscription is None:
            raise NotFound("Aucun abonnement pour cette organisation.")
        return Response(SubscriptionSerializer(subscription).data)


class InvoiceListView(OrganizationContextMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(organization=self.request.organization)


def _get_plan(plan_code):
    try:
        return Plan.objects.get(code=plan_code, is_active=True)
    except Plan.DoesNotExist as exc:
        raise ValidationError("Plan introuvable ou inactif.") from exc


def _get_or_create_subscription(organization, plan, provider):
    subscription = getattr(organization, "subscription", None)
    if subscription is None:
        return SubscriptionService.start_subscription(organization=organization, plan=plan, provider=provider)
    subscription.plan = plan
    subscription.provider = provider
    subscription.save(update_fields=["plan", "provider", "updated_at"])
    return subscription


class CheckoutStripeView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = CheckoutStripeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = _get_plan(serializer.validated_data["plan_code"])
        subscription = _get_or_create_subscription(request.organization, plan, Subscription.Provider.STRIPE)
        try:
            result = get_provider("stripe").create_checkout(
                organization=request.organization, plan=plan, subscription=subscription
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)


class CheckoutMobileMoneyView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = CheckoutMobileMoneySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = _get_plan(serializer.validated_data["plan_code"])
        subscription = _get_or_create_subscription(request.organization, plan, Subscription.Provider.MOBILE_MONEY)
        subscription.metadata = {**(subscription.metadata or {}), "phone_number": serializer.validated_data["phone_number"]}
        subscription.save(update_fields=["metadata", "updated_at"])
        try:
            result = get_provider("mobile_money").create_checkout(
                organization=request.organization,
                plan=plan,
                subscription=subscription,
                phone_number=serializer.validated_data["phone_number"],
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)


class CheckoutBankTransferView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = CheckoutBankTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = _get_plan(serializer.validated_data["plan_code"])
        subscription = _get_or_create_subscription(request.organization, plan, Subscription.Provider.BANK_TRANSFER)
        result = get_provider("bank_transfer").create_checkout(
            organization=request.organization, plan=plan, subscription=subscription
        )
        return Response(result)


class SubscriptionCancelView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        subscription = getattr(request.organization, "subscription", None)
        if subscription is None:
            raise NotFound("Aucun abonnement pour cette organisation.")
        get_provider(subscription.provider).cancel(subscription=subscription)
        SubscriptionService.cancel(subscription=subscription)
        return Response(SubscriptionSerializer(subscription).data)


class InvoiceProofUploadView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request, invoice_id):
        invoice = get_object_or_404(
            Invoice, pk=invoice_id, organization=request.organization, provider=Subscription.Provider.BANK_TRANSFER
        )
        serializer = InvoiceProofUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice.proof_file = serializer.validated_data["proof"]
        invoice.status = Invoice.Status.PENDING_REVIEW
        invoice.save(update_fields=["proof_file", "status", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)


class InvoiceReviewView(APIView):
    """Validation manuelle d'un virement par un membre de l'équipe plateforme
    (is_staff) — pas par un admin de l'organisation cliente elle-même."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, invoice_id):
        approve = bool(request.data.get("approve", True))
        invoice = get_object_or_404(Invoice, pk=invoice_id, provider=Subscription.Provider.BANK_TRANSFER)
        if invoice.status != Invoice.Status.PENDING_REVIEW:
            raise ValidationError("Cette facture n'est pas en attente de validation.")

        invoice.reviewed_by = request.user
        if approve:
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=["status", "paid_at", "reviewed_by", "updated_at"])
            SubscriptionService.renew(subscription=invoice.subscription)
        else:
            invoice.status = Invoice.Status.FAILED
            invoice.save(update_fields=["status", "reviewed_by", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)


class StripeWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        provider = StripeProvider()
        if not provider.enabled:
            return Response(status=204)
        try:
            provider.handle_webhook(payload=request.body, sig_header=request.headers.get("Stripe-Signature", ""))
        except Exception:
            logger.exception("Échec du traitement du webhook Stripe.")
            return Response(status=400)
        return Response(status=200)


class CamPayWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        from django.conf import settings as django_settings

        provided_secret = request.headers.get("X-Webhook-Secret", "")
        if django_settings.CAMPAY_WEBHOOK_SECRET and provided_secret != django_settings.CAMPAY_WEBHOOK_SECRET:
            raise PermissionDenied("Signature de webhook invalide.")
        CamPayProvider().handle_webhook(payload=request.data)
        return Response(status=200)
