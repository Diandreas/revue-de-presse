from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import Invoice, Subscription
from apps.billing.providers.campay_provider import CamPayProvider
from apps.billing.providers.stripe_provider import StripeProvider, _stripe_amount_to_decimal
from tests.factories import OrganizationFactory, PlanFactory, SubscriptionFactory


def test_stripe_amount_to_decimal_does_not_divide_zero_decimal_currencies():
    # XAF est une devise "zero-decimal" chez Stripe : 50000 signifie déjà 50000 XAF,
    # pas 500.00 XAF. C'est aussi la devise par défaut de nos Plan.
    assert _stripe_amount_to_decimal(50000, "xaf") == 50000
    assert _stripe_amount_to_decimal(50000, "XAF") == 50000


def test_stripe_amount_to_decimal_divides_regular_currencies():
    assert _stripe_amount_to_decimal(1999, "eur") == 19.99
    assert _stripe_amount_to_decimal(None, "usd") == 0


@pytest.mark.django_db
def test_campay_webhook_marks_invoice_paid_and_renews_subscription():
    org = OrganizationFactory()
    plan = PlanFactory()
    subscription = SubscriptionFactory(
        organization=org, plan=plan, provider=Subscription.Provider.MOBILE_MONEY, status=Subscription.Status.INCOMPLETE
    )
    invoice = Invoice.objects.create(
        organization=org,
        subscription=subscription,
        provider=Subscription.Provider.MOBILE_MONEY,
        provider_reference="ref-123",
        amount=plan.price_amount,
        period_start=timezone.now(),
        period_end=timezone.now() + timedelta(days=30),
    )

    CamPayProvider().handle_webhook(payload={"external_reference": "ref-123", "status": "SUCCESSFUL"})

    invoice.refresh_from_db()
    subscription.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    assert invoice.paid_at is not None
    assert subscription.status == Subscription.Status.ACTIVE


@pytest.mark.django_db
def test_campay_webhook_failed_status_marks_invoice_failed_without_renewing():
    org = OrganizationFactory()
    plan = PlanFactory()
    subscription = SubscriptionFactory(
        organization=org, plan=plan, provider=Subscription.Provider.MOBILE_MONEY, status=Subscription.Status.INCOMPLETE
    )
    invoice = Invoice.objects.create(
        organization=org,
        subscription=subscription,
        provider=Subscription.Provider.MOBILE_MONEY,
        provider_reference="ref-456",
        amount=plan.price_amount,
        period_start=timezone.now(),
        period_end=timezone.now() + timedelta(days=30),
    )

    CamPayProvider().handle_webhook(payload={"external_reference": "ref-456", "status": "FAILED"})

    invoice.refresh_from_db()
    subscription.refresh_from_db()
    assert invoice.status == Invoice.Status.FAILED
    assert subscription.status == Subscription.Status.INCOMPLETE


@pytest.mark.django_db
def test_campay_webhook_unknown_reference_is_noop():
    result = CamPayProvider().handle_webhook(payload={"external_reference": "does-not-exist", "status": "SUCCESSFUL"})
    assert result is None


@pytest.mark.django_db
def test_stripe_checkout_completed_activates_subscription():
    org = OrganizationFactory()
    plan = PlanFactory()
    subscription = SubscriptionFactory(
        organization=org, plan=plan, provider=Subscription.Provider.STRIPE, status=Subscription.Status.INCOMPLETE
    )

    StripeProvider()._handle_checkout_completed(
        {
            "metadata": {"subscription_id": str(subscription.id)},
            "customer": "cus_123",
            "subscription": "sub_123",
        }
    )

    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.provider_customer_id == "cus_123"
    assert subscription.provider_subscription_id == "sub_123"


@pytest.mark.django_db
def test_stripe_payment_failed_marks_past_due():
    org = OrganizationFactory()
    plan = PlanFactory()
    subscription = SubscriptionFactory(
        organization=org,
        plan=plan,
        provider=Subscription.Provider.STRIPE,
        status=Subscription.Status.ACTIVE,
        provider_subscription_id="sub_123",
    )

    StripeProvider()._handle_payment_failed({"subscription": "sub_123"})

    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.PAST_DUE


@pytest.mark.django_db
def test_stripe_subscription_deleted_cancels_subscription():
    org = OrganizationFactory()
    plan = PlanFactory()
    subscription = SubscriptionFactory(
        organization=org,
        plan=plan,
        provider=Subscription.Provider.STRIPE,
        status=Subscription.Status.ACTIVE,
        provider_subscription_id="sub_789",
    )

    StripeProvider()._handle_subscription_deleted({"id": "sub_789"})

    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.CANCELED



def _invoice(provider, reference, status=Invoice.Status.PENDING):
    org = OrganizationFactory()
    plan = PlanFactory()
    subscription = SubscriptionFactory(organization=org, plan=plan, provider=provider, status=Subscription.Status.INCOMPLETE)
    return Invoice.objects.create(
        organization=org, subscription=subscription, provider=provider, provider_reference=reference, status=status,
        amount=plan.price_amount, period_start=timezone.now(), period_end=timezone.now() + timedelta(days=30),
    )


@pytest.mark.django_db
def test_campay_webhook_is_closed_when_no_secret_is_configured(api_client, settings):
    """Faille constatée en prod : secret vide = aucune vérification, n'importe qui « payait »."""
    settings.CAMPAY_WEBHOOK_SECRET = ""
    invoice = _invoice(Subscription.Provider.BANK_TRANSFER, "")

    response = api_client.post("/api/billing/webhooks/campay/", {"external_reference": "", "status": "SUCCESSFUL"}, format="json")

    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING


@pytest.mark.django_db
def test_campay_webhook_rejects_a_wrong_secret(api_client, settings):
    settings.CAMPAY_WEBHOOK_SECRET = "s3cret"
    invoice = _invoice(Subscription.Provider.MOBILE_MONEY, "ref-1")

    response = api_client.post(
        "/api/billing/webhooks/campay/", {"external_reference": "ref-1", "status": "SUCCESSFUL"},
        format="json", HTTP_X_WEBHOOK_SECRET="nope",
    )

    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING


@pytest.mark.django_db
def test_campay_webhook_with_the_secret_pays_the_pending_mobile_money_invoice(api_client, settings):
    settings.CAMPAY_WEBHOOK_SECRET = "s3cret"
    invoice = _invoice(Subscription.Provider.MOBILE_MONEY, "ref-2")

    response = api_client.post(
        "/api/billing/webhooks/campay/", {"external_reference": "ref-2", "status": "SUCCESSFUL"},
        format="json", HTTP_X_WEBHOOK_SECRET="s3cret",
    )

    assert response.status_code == 200
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID


@pytest.mark.django_db
def test_campay_webhook_never_settles_bank_transfer_paid_or_unreferenced_invoices():
    transfer = _invoice(Subscription.Provider.BANK_TRANSFER, "")
    paid = _invoice(Subscription.Provider.MOBILE_MONEY, "ref-paid", status=Invoice.Status.PAID)

    assert CamPayProvider().handle_webhook(payload={"external_reference": "", "status": "SUCCESSFUL"}) is None
    assert CamPayProvider().handle_webhook(payload={"status": "SUCCESSFUL"}) is None
    assert CamPayProvider().handle_webhook(payload={"external_reference": "ref-paid", "status": "FAILED"}) is None

    transfer.refresh_from_db()
    paid.refresh_from_db()
    assert transfer.status == Invoice.Status.PENDING
    assert paid.status == Invoice.Status.PAID
