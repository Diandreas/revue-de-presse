"""Choisir une formule ne doit rien accorder tant que le paiement n'est pas confirmé."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.billing.models import Invoice, Subscription
from apps.billing.providers import StripeProvider
from apps.billing.services import SubscriptionService
from tests.factories import PlanFactory, SubscriptionFactory, UserFactory
from tests.pdf_fixtures import make_minimal_pdf_bytes


@pytest.fixture
def plans(db):
    return (
        PlanFactory(code="starter", name="Starter", price_amount=50000, max_reviews_per_month=10),
        PlanFactory(code="pro", name="Pro", price_amount=150000, max_reviews_per_month=40),
    )


def _trial(organization, plan):
    now = timezone.now()
    return SubscriptionFactory(
        organization=organization,
        plan=plan,
        status=Subscription.Status.TRIALING,
        current_period_start=now,
        current_period_end=now + timedelta(days=14),
        metadata={"trial": True},
    )


@pytest.mark.django_db
def test_starting_a_payment_for_a_bigger_plan_does_not_raise_the_quota(authenticated_client, organization, plans):
    """Régression : le clic sur « Payer » (prestataire non configuré, paiement abandonné…)
    basculait immédiatement l'abonnement actif sur la formule supérieure."""
    starter, _pro = plans
    subscription = SubscriptionFactory(organization=organization, plan=starter, status=Subscription.Status.ACTIVE)

    for endpoint in ("stripe", "bank-transfer"):
        response = authenticated_client.post(f"/api/billing/checkout/{endpoint}/", {"plan_code": "pro"})
        assert response.status_code == 200, response.data

    subscription.refresh_from_db()
    assert subscription.plan == starter
    assert subscription.provider == Subscription.Provider.BANK_TRANSFER
    data = authenticated_client.get("/api/billing/subscription/").data
    assert data["reviews_limit"] == 10
    assert data["pending_plan_code"] == "pro"


@pytest.mark.django_db
def test_validated_bank_transfer_applies_the_requested_plan(authenticated_client, organization, plans, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    starter, pro = plans
    subscription = _trial(organization, starter)

    response = authenticated_client.post("/api/billing/checkout/bank-transfer/", {"plan_code": "pro"})
    assert response.status_code == 200, response.data
    invoice = Invoice.objects.get(pk=response.data["invoice_id"])
    assert invoice.amount == pro.price_amount
    subscription.refresh_from_db()
    assert subscription.plan == starter  # l'essai continue sur sa formule en attendant le virement

    proof = SimpleUploadedFile("recu.pdf", make_minimal_pdf_bytes(["Justificatif"]), content_type="application/pdf")
    response = authenticated_client.post(f"/api/billing/invoices/{invoice.id}/proof/", {"proof": proof}, format="multipart")
    assert response.status_code == 200, response.data

    staff = UserFactory(is_staff=True)
    staff_client = APIClient()
    staff_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(staff).access_token}")
    response = staff_client.post(f"/api/billing/invoices/{invoice.id}/review/", {"approve": True}, format="json")
    assert response.status_code == 200, response.data

    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.plan == pro
    assert subscription.provider == Subscription.Provider.BANK_TRANSFER
    assert "pending_plan_code" not in subscription.metadata


@pytest.mark.django_db
def test_unconfigured_card_or_mobile_money_payment_leaves_the_subscription_untouched(
    authenticated_client, organization, plans
):
    starter, _pro = plans
    subscription = _trial(organization, starter)

    card = authenticated_client.post("/api/billing/checkout/stripe/", {"plan_code": "pro"})
    momo = authenticated_client.post(
        "/api/billing/checkout/mobile-money/", {"plan_code": "pro", "phone_number": "237670000000"}
    )

    assert card.status_code == 200 and card.data["mock"] is True
    assert momo.status_code == 200 and momo.data["mock"] is True
    subscription.refresh_from_db()
    assert subscription.metadata == {"trial": True}
    assert subscription.provider == Subscription.Provider.BANK_TRANSFER


@pytest.mark.django_db
def test_without_current_access_the_chosen_plan_applies_immediately(authenticated_client, organization, plans):
    starter, pro = plans
    subscription = SubscriptionFactory(organization=organization, plan=starter, status=Subscription.Status.CANCELED)

    response = authenticated_client.post("/api/billing/checkout/bank-transfer/", {"plan_code": "pro"})
    assert response.status_code == 200, response.data

    subscription.refresh_from_db()
    assert subscription.plan == pro
    assert "pending_plan_code" not in subscription.metadata


@pytest.mark.django_db
def test_choosing_the_current_plan_again_cancels_a_pending_change(organization, plans):
    starter, _pro = plans
    subscription = SubscriptionFactory(
        organization=organization, plan=starter, status=Subscription.Status.ACTIVE, metadata={"pending_plan_code": "pro"}
    )

    SubscriptionService.request_plan_change(
        subscription=subscription, plan=starter, provider=Subscription.Provider.BANK_TRANSFER
    )

    subscription.refresh_from_db()
    assert subscription.plan == starter
    assert "pending_plan_code" not in subscription.metadata


@pytest.mark.django_db
def test_stripe_activation_applies_the_pending_plan_and_provider(organization, plans):
    starter, pro = plans
    subscription = _trial(organization, starter)
    subscription.metadata = {"trial": True, "pending_plan_code": "pro"}
    subscription.save()

    StripeProvider()._handle_checkout_completed(
        {"metadata": {"subscription_id": str(subscription.id)}, "customer": "cus_1", "subscription": "sub_1"}
    )

    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.plan == pro
    assert subscription.provider == Subscription.Provider.STRIPE
    assert "pending_plan_code" not in subscription.metadata
