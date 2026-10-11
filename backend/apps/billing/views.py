import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsOrgAdmin, IsOrgMember, OrganizationContextMixin

from .invoice_pdf import invoice_filename, render_invoice_pdf
from .models import BillingProfile, Invoice, Plan, Subscription
from .providers import get_provider
from .providers.campay_provider import CamPayProvider
from .providers.stripe_provider import StripeProvider
from .serializers import (
    BillingProfileSerializer,
    CheckoutBankTransferSerializer,
    CheckoutMobileMoneySerializer,
    CheckoutStripeSerializer,
    InvoiceProofUploadSerializer,
    InvoiceReviewSerializer,
    InvoiceSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)
from .services import InvoiceError, InvoiceService, SubscriptionService, billing_is_manual, manual_billing_message

logger = logging.getLogger(__name__)


def _refuse_in_manual_mode():
    """Mode manuel : aucun parcours de paiement en libre-service, le client passe par l'équipe."""
    if billing_is_manual():
        raise PermissionDenied(manual_billing_message())


class PlanListView(generics.ListAPIView):
    """Formules actives et leurs limites. Public (vitrine) : les prix n'y figurent jamais
    pour un non-membre de l'équipe (cf. PlanSerializer)."""

    permission_classes = [AllowAny]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(is_active=True)


class SubscriptionMeView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request):
        subscription = getattr(request.organization, "subscription", None)
        if subscription is None:
            raise NotFound("Aucun abonnement pour cette organisation.")
        return Response(SubscriptionSerializer(subscription, context={"request": request}).data)


class InvoiceListView(OrganizationContextMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(organization=self.request.organization).select_related("plan")


class InvoicePdfView(APIView):
    """PDF d'une facture (proforma ou acquittée) : membres de l'organisation et équipe."""

    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        from apps.accounts.models import Membership

        invoice = get_object_or_404(Invoice.objects.select_related("plan"), pk=invoice_id)
        is_member = invoice.organization_id is not None and Membership.objects.filter(
            organization_id=invoice.organization_id, user=request.user
        ).exists()
        if not (request.user.is_staff or is_member):
            raise NotFound("Facture introuvable.")
        try:
            pdf_bytes = render_invoice_pdf(invoice)
        except OSError:
            # WeasyPrint sans ses bibliothèques natives (Pango/cairo) sur ce serveur.
            logger.exception("Génération du PDF de facture impossible.")
            return Response({"detail": "Le PDF de la facture ne peut pas être généré pour le moment."}, status=503)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice_filename(invoice)}"'
        return response


class BillingProfileView(OrganizationContextMixin, APIView):
    """Informations de facturation (raison sociale, NIU, RCCM) reportées sur les factures."""

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsAuthenticated(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]

    def get(self, request):
        profile = BillingProfile.objects.filter(organization=request.organization).first()
        if profile is None:
            return Response(BillingProfileSerializer(BillingProfile(legal_name=request.organization.name)).data)
        return Response(BillingProfileSerializer(profile).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, *, partial):
        profile, _created = BillingProfile.objects.get_or_create(organization=request.organization)
        serializer = BillingProfileSerializer(profile, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def _get_plan(plan_code):
    try:
        return Plan.objects.get(code=plan_code, is_active=True)
    except Plan.DoesNotExist as exc:
        raise ValidationError("Plan introuvable ou inactif.") from exc


def _get_or_create_subscription(organization, plan, provider):
    subscription = getattr(organization, "subscription", None)
    if subscription is None:
        return SubscriptionService.start_subscription(organization=organization, plan=plan, provider=provider)
    return SubscriptionService.request_plan_change(subscription=subscription, plan=plan, provider=provider)


class CheckoutStripeView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        _refuse_in_manual_mode()
        serializer = CheckoutStripeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = _get_plan(serializer.validated_data["plan_code"])
        provider = get_provider("stripe")
        if not provider.enabled:
            # Prestataire non configuré : réponse explicative, sans toucher à l'abonnement.
            return Response(provider.create_checkout(organization=request.organization, plan=plan, subscription=None))
        subscription = _get_or_create_subscription(request.organization, plan, Subscription.Provider.STRIPE)
        try:
            result = provider.create_checkout(organization=request.organization, plan=plan, subscription=subscription)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(result)


class CheckoutMobileMoneyView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        _refuse_in_manual_mode()
        serializer = CheckoutMobileMoneySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = _get_plan(serializer.validated_data["plan_code"])
        provider = get_provider("mobile_money")
        if not provider.enabled:
            return Response(provider.create_checkout(organization=request.organization, plan=plan, subscription=None))
        subscription = _get_or_create_subscription(request.organization, plan, Subscription.Provider.MOBILE_MONEY)
        subscription.metadata = {**(subscription.metadata or {}), "phone_number": serializer.validated_data["phone_number"]}
        subscription.save(update_fields=["metadata", "updated_at"])
        try:
            result = provider.create_checkout(
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
        _refuse_in_manual_mode()
        serializer = CheckoutBankTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = _get_plan(serializer.validated_data["plan_code"])
        subscription = _get_or_create_subscription(request.organization, plan, Subscription.Provider.BANK_TRANSFER)
        result = get_provider("bank_transfer").create_checkout(
            organization=request.organization, plan=plan, subscription=subscription
        )
        return Response(result)


class SubscriptionCancelView(OrganizationContextMixin, APIView):
    """Résiliation : une période payée en cours va jusqu'à son terme (voir
    SubscriptionService.request_cancellation). Stripe garde sa résiliation immédiate."""

    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        subscription = getattr(request.organization, "subscription", None)
        if subscription is None:
            raise NotFound("Aucun abonnement pour cette organisation.")
        if subscription.provider == Subscription.Provider.STRIPE:
            get_provider(subscription.provider).cancel(subscription=subscription)
            SubscriptionService.cancel(subscription=subscription)
        else:
            SubscriptionService.request_cancellation(subscription=subscription)
        return Response(SubscriptionSerializer(subscription, context={"request": request}).data)


class SubscriptionResumeView(OrganizationContextMixin, APIView):
    """Annule une résiliation programmée en fin de période."""

    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        subscription = getattr(request.organization, "subscription", None)
        if subscription is None:
            raise NotFound("Aucun abonnement pour cette organisation.")
        try:
            SubscriptionService.resume(subscription=subscription)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(SubscriptionSerializer(subscription, context={"request": request}).data)


class InvoiceProofUploadView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request, invoice_id):
        _refuse_in_manual_mode()
        invoice = get_object_or_404(
            Invoice, pk=invoice_id, organization=request.organization, provider=Subscription.Provider.BANK_TRANSFER
        )
        # Un justificatif ne vaut que pour une facture encore à régler : le renvoyer sur une
        # facture payée (ou refusée) la remettait en validation pour une seconde prolongation.
        if invoice.status != Invoice.Status.PENDING:
            raise ValidationError("Cette facture n'attend pas de justificatif.")
        serializer = InvoiceProofUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice.proof_file = serializer.validated_data["proof"]
        invoice.status = Invoice.Status.PENDING_REVIEW
        invoice.save(update_fields=["proof_file", "status", "updated_at"])
        return Response(InvoiceSerializer(invoice).data)


class InvoiceReviewView(APIView):
    """Validation ou refus d'un virement par un membre de l'équipe plateforme (is_staff) —
    pas par un admin de l'organisation cliente elle-même. Reste ouvert en mode manuel."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, invoice_id):
        serializer = InvoiceReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = get_object_or_404(Invoice, pk=invoice_id, provider=Subscription.Provider.BANK_TRANSFER)
        if invoice.status != Invoice.Status.PENDING_REVIEW:
            raise ValidationError("Cette facture n'est pas en attente de validation.")
        try:
            if serializer.validated_data["approve"]:
                invoice = InvoiceService.settle(invoice=invoice, reviewed_by=request.user)
            else:
                invoice = InvoiceService.reject(
                    invoice=invoice, reviewed_by=request.user, reason=serializer.validated_data.get("reason", "")
                )
        except InvoiceError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(InvoiceSerializer(invoice).data)


class StripeWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        provider = StripeProvider()
        # Sans secret de signature, construct_event accepterait une signature calculée avec une
        # clé vide : n'importe qui pourrait « confirmer » un paiement. Webhook fermé.
        if not provider.enabled or not settings.STRIPE_WEBHOOK_SECRET:
            raise PermissionDenied("Webhook Stripe non configuré.")
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
        import hmac

        # Sans secret configuré (CamPay désactivé), le webhook est fermé : sinon n'importe qui
        # pourrait « confirmer » un paiement et s'offrir un abonnement.
        expected = settings.CAMPAY_WEBHOOK_SECRET
        provided_secret = request.headers.get("X-Webhook-Secret", "")
        if not expected or not hmac.compare_digest(provided_secret.encode(), expected.encode()):
            raise PermissionDenied("Signature de webhook invalide.")
        CamPayProvider().handle_webhook(payload=request.data)
        return Response(status=200)
