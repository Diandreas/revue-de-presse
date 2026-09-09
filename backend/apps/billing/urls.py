from django.urls import path

from .views import (
    CamPayWebhookView,
    CheckoutBankTransferView,
    CheckoutMobileMoneyView,
    CheckoutStripeView,
    InvoiceListView,
    InvoiceProofUploadView,
    InvoiceReviewView,
    PlanListView,
    StripeWebhookView,
    SubscriptionCancelView,
    SubscriptionMeView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="billing-plans"),
    path("subscription/", SubscriptionMeView.as_view(), name="billing-subscription"),
    path("subscription/cancel/", SubscriptionCancelView.as_view(), name="billing-subscription-cancel"),
    path("invoices/", InvoiceListView.as_view(), name="billing-invoices"),
    path("invoices/<uuid:invoice_id>/proof/", InvoiceProofUploadView.as_view(), name="billing-invoice-proof"),
    path("invoices/<uuid:invoice_id>/review/", InvoiceReviewView.as_view(), name="billing-invoice-review"),
    path("checkout/stripe/", CheckoutStripeView.as_view(), name="billing-checkout-stripe"),
    path("checkout/mobile-money/", CheckoutMobileMoneyView.as_view(), name="billing-checkout-mobile-money"),
    path("checkout/bank-transfer/", CheckoutBankTransferView.as_view(), name="billing-checkout-bank-transfer"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="billing-webhook-stripe"),
    path("webhooks/campay/", CamPayWebhookView.as_view(), name="billing-webhook-campay"),
]
