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
