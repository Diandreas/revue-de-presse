"""Facturation en mode manuel : paiements en ligne fermés, l'équipe active / prolonge les
abonnements dans l'admin, accès borné par la fin de période (+ délai de grâce), factures
conformes et prix jamais exposés aux clients."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Invitation, Membership
from apps.billing import tasks
from apps.billing.invoice_pdf import build_invoice_html
from apps.billing.invoicing import add_months, amount_in_words, amounts_from_ht, amounts_from_ttc
from apps.billing.models import BillingProfile, Invoice, Subscription
from apps.billing.services import (
    SUBSCRIPTION_EXPIRED_MESSAGE,
    TRIAL_EXPIRED_MESSAGE,
    InvoiceService,
    SubscriptionService,
    seats_available,
    seats_used,
)
from apps.press_review.models import PressReviewJob
from tests.factories import MembershipFactory, OrganizationFactory, PlanFactory, SubscriptionFactory, UserFactory


def _client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


@pytest.fixture
def staff_client(db):
    return _client_for(UserFactory(is_staff=True))


@pytest.fixture
def starter(db):
    return PlanFactory(code="starter", name="Starter", price_amount=50000, max_reviews_per_month=10, max_seats=3)


@pytest.fixture
def pro(db):
    return PlanFactory(code="pro", name="Pro", price_amount=150000, max_reviews_per_month=40, max_seats=10)


def _subscription(organization, plan, status=Subscription.Status.ACTIVE, *, ends_in=None, started_ago=10, **extra):
    now = timezone.now()
    return SubscriptionFactory(
        organization=organization,
        plan=plan,
        status=status,
        current_period_start=now - timedelta(days=started_ago),
        current_period_end=None if ends_in is None else now + ends_in,
        **extra,
    )


def _pending_transfer_invoice(subscription, plan, *, status=Invoice.Status.PENDING_REVIEW):
    invoice = InvoiceService.create_for_plan(
        subscription=subscription, plan=plan, provider=Subscription.Provider.BANK_TRANSFER
    )
    if status != Invoice.Status.PENDING:
        invoice.status = status
        invoice.save(update_fields=["status"])
    return invoice


# --------------------------------------------------------------------------- mode manuel


@pytest.mark.django_db
@pytest.mark.parametrize(
    "endpoint, payload",
    [
        ("stripe", {"plan_code": "pro"}),
        ("mobile-money", {"plan_code": "pro", "phone_number": "237670000000"}),
        ("bank-transfer", {"plan_code": "pro"}),
    ],
)
def test_manual_mode_closes_every_self_serve_checkout(authenticated_client, organization, starter, pro, endpoint, payload):
    subscription = _subscription(organization, starter, ends_in=timedelta(days=5))

    response = authenticated_client.post(f"/api/billing/checkout/{endpoint}/", payload, format="json")

    assert response.status_code == 403
    assert "WhatsApp" in response.data["detail"] and "+237 693 42 79 13" in response.data["detail"]
    subscription.refresh_from_db()
    assert subscription.plan == starter and "pending_plan_code" not in subscription.metadata
    assert not Invoice.objects.exists()


@pytest.mark.django_db
def test_manual_mode_refuses_proof_upload(authenticated_client, organization, starter, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    subscription = _subscription(organization, starter, ends_in=timedelta(days=5))
    invoice = _pending_transfer_invoice(subscription, starter, status=Invoice.Status.PENDING)
    proof = SimpleUploadedFile("recu.pdf", b"%PDF-1.4", content_type="application/pdf")

    response = authenticated_client.post(f"/api/billing/invoices/{invoice.id}/proof/", {"proof": proof}, format="multipart")

    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING


@pytest.mark.django_db
def test_mobile_money_renewal_task_does_nothing_in_manual_mode(starter):
    _subscription(
        OrganizationFactory(), starter, ends_in=timedelta(days=2),
        provider=Subscription.Provider.MOBILE_MONEY, metadata={"phone_number": "237670000000"},
    )
    with mock.patch("apps.billing.tasks.get_provider") as get_provider:
        assert tasks.request_monthly_mobile_money_renewals() == 0
    get_provider.assert_not_called()


@pytest.mark.django_db
def test_stripe_webhook_is_closed_without_a_signing_secret(api_client, settings):
    settings.STRIPE_SECRET_KEY = "sk_test_factice"
    settings.STRIPE_WEBHOOK_SECRET = ""
    with mock.patch("apps.billing.providers.stripe_provider.StripeProvider.handle_webhook") as handle:
        response = api_client.post("/api/billing/webhooks/stripe/", {"type": "invoice.paid"}, format="json")
    assert response.status_code == 403
    handle.assert_not_called()


@pytest.mark.django_db
def test_stripe_webhook_with_a_secret_still_checks_the_signature(api_client, settings):
    settings.STRIPE_SECRET_KEY = "sk_test_factice"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_factice"
    response = api_client.post(
        "/api/billing/webhooks/stripe/", {"type": "invoice.paid"}, format="json", HTTP_STRIPE_SIGNATURE="t=1,v1=faux"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_periodic_tasks_are_created_by_migration_with_mobile_money_disabled():
    import importlib

    from django.apps import apps as registry

    migration = importlib.import_module("apps.billing.migrations.0005_periodic_tasks")
    PeriodicTask.objects.filter(task__startswith="apps.billing.tasks.").delete()

    migration.create_tasks(registry, None)

    tasks_by_name = {task.name: task for task in PeriodicTask.objects.filter(task__startswith="apps.billing.tasks.")}
    assert tasks_by_name["Vérification des abonnements en retard"].enabled is True
    assert tasks_by_name["Rappels de renouvellement"].enabled is True
    assert tasks_by_name["Relances mensuelles Mobile Money"].enabled is False


@pytest.mark.django_db
def test_seed_periodic_tasks_command_follows_the_billing_mode(settings):
    from django.core.management import call_command

    settings.BILLING_MODE = "online"
    call_command("seed_periodic_tasks")
    assert PeriodicTask.objects.get(name="Relances mensuelles Mobile Money").enabled is True

    settings.BILLING_MODE = "manual"
    call_command("seed_periodic_tasks")
    assert PeriodicTask.objects.get(name="Relances mensuelles Mobile Money").enabled is False


# --------------------------------------------------------------------------- virement : validation staff


@pytest.mark.django_db
def test_proof_can_only_be_attached_to_a_pending_invoice(authenticated_client, organization, starter, settings, tmp_path):
    settings.BILLING_MODE = "online"
    settings.MEDIA_ROOT = tmp_path
    subscription = _subscription(organization, starter, ends_in=timedelta(days=5))
    paid = _pending_transfer_invoice(subscription, starter, status=Invoice.Status.PAID)
    proof = SimpleUploadedFile("recu.pdf", b"%PDF-1.4", content_type="application/pdf")

    response = authenticated_client.post(f"/api/billing/invoices/{paid.id}/proof/", {"proof": proof}, format="multipart")

    assert response.status_code == 400
    paid.refresh_from_db()
    assert paid.status == Invoice.Status.PAID


@pytest.mark.django_db
def test_staff_review_reads_approve_as_a_real_boolean(staff_client, starter):
    """Régression : approve="false" était traité comme une approbation."""
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.CANCELED)
    invoice = _pending_transfer_invoice(subscription, starter)

    response = staff_client.post(
        f"/api/billing/invoices/{invoice.id}/review/", {"approve": "false", "reason": "Montant non reçu"}, format="json"
    )

    assert response.status_code == 200, response.data
    invoice.refresh_from_db()
    subscription.refresh_from_db()
    assert invoice.status == Invoice.Status.FAILED
    assert invoice.notes == "Montant non reçu"
    assert subscription.status == Subscription.Status.CANCELED


@pytest.mark.django_db
def test_staff_review_requires_an_explicit_decision(staff_client, starter):
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.CANCELED)
    invoice = _pending_transfer_invoice(subscription, starter)

    response = staff_client.post(f"/api/billing/invoices/{invoice.id}/review/", {}, format="json")

    assert response.status_code == 400
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING_REVIEW


@pytest.mark.django_db
def test_review_is_forbidden_to_the_customer_even_an_owner(authenticated_client, organization, starter):
    subscription = _subscription(organization, starter, Subscription.Status.CANCELED)
    invoice = _pending_transfer_invoice(subscription, starter)

    response = authenticated_client.post(f"/api/billing/invoices/{invoice.id}/review/", {"approve": True}, format="json")

    assert response.status_code == 403
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING_REVIEW


@pytest.mark.django_db
def test_validating_an_invoice_applies_the_plan_it_paid_for_not_a_later_pending_one(staff_client, starter, pro):
    """Faille : payer Starter, puis demander Enterprise et faire valider la facture Starter
    donnait la formule supérieure."""
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.CANCELED)
    invoice = _pending_transfer_invoice(subscription, starter)
    subscription.metadata = {"pending_plan_code": pro.code}
    subscription.save()

    response = staff_client.post(f"/api/billing/invoices/{invoice.id}/review/", {"approve": True}, format="json")

    assert response.status_code == 200, response.data
    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.plan == starter
    assert subscription.metadata.get("pending_plan_code") == pro.code  # reste à payer


@pytest.mark.django_db
def test_validation_refuses_an_amount_that_no_longer_covers_the_plan(staff_client, starter):
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.CANCELED)
    invoice = _pending_transfer_invoice(subscription, starter)
    starter.price_amount = 80000
    starter.save()

    response = staff_client.post(f"/api/billing/invoices/{invoice.id}/review/", {"approve": True}, format="json")

    assert response.status_code == 400
    assert "Montant insuffisant" in response.data["detail"]
    invoice.refresh_from_db()
    subscription.refresh_from_db()
    assert invoice.status == Invoice.Status.PENDING_REVIEW
    assert subscription.status == Subscription.Status.CANCELED


@pytest.mark.django_db
def test_an_invoice_cannot_be_settled_twice(starter):
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.CANCELED)
    invoice = _pending_transfer_invoice(subscription, starter)
    InvoiceService.settle(invoice=invoice)
    end_after_first = Subscription.objects.get(pk=subscription.pk).current_period_end

    with pytest.raises(ValueError):
        InvoiceService.settle(invoice=invoice)
    assert Subscription.objects.get(pk=subscription.pk).current_period_end == end_after_first


# --------------------------------------------------------------------------- accès et échéances


@pytest.mark.django_db
def test_active_subscription_keeps_access_during_the_grace_period_only(starter, settings):
    settings.BILLING_GRACE_DAYS = 3
    org = OrganizationFactory()
    subscription = _subscription(org, starter, ends_in=-timedelta(days=2))
    assert SubscriptionService.grants_access(subscription) is True

    subscription.current_period_end = timezone.now() - timedelta(days=4)
    subscription.save()
    assert SubscriptionService.grants_access(subscription) is False
    assert SubscriptionService.review_quota_denial(organization=org) == SUBSCRIPTION_EXPIRED_MESSAGE


@pytest.mark.django_db
def test_trial_ends_exactly_at_its_end_date_without_grace(starter):
    org = OrganizationFactory()
    subscription = _subscription(org, starter, Subscription.Status.TRIALING, ends_in=-timedelta(minutes=1))
    assert SubscriptionService.grants_access(subscription) is False
    assert SubscriptionService.review_quota_denial(organization=org) == TRIAL_EXPIRED_MESSAGE


@pytest.mark.django_db
def test_past_due_keeps_access_until_the_end_of_the_grace_period(starter):
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.PAST_DUE, ends_in=-timedelta(days=1))
    assert SubscriptionService.grants_access(subscription) is True
    subscription.current_period_end = None
    assert SubscriptionService.grants_access(subscription) is False


@pytest.mark.django_db
def test_overdue_check_follows_the_same_rules_as_access(starter):
    org_expired, org_resigned, org_trial, org_stripe = (OrganizationFactory() for _ in range(4))
    expired = _subscription(org_expired, starter, ends_in=-timedelta(days=1), provider=Subscription.Provider.MANUAL)
    resigned = _subscription(org_resigned, starter, ends_in=-timedelta(hours=1), cancel_at_period_end=True)
    trial = _subscription(org_trial, starter, Subscription.Status.TRIALING, ends_in=-timedelta(days=1))
    stripe = _subscription(org_stripe, starter, ends_in=-timedelta(days=10), provider=Subscription.Provider.STRIPE)

    tasks.check_overdue_subscriptions()

    for subscription in (expired, resigned, trial, stripe):
        subscription.refresh_from_db()
    assert expired.status == Subscription.Status.PAST_DUE
    assert SubscriptionService.grants_access(expired) is True  # encore dans la grâce : pas coupé à J+1
    assert resigned.status == Subscription.Status.CANCELED
    assert trial.status == Subscription.Status.TRIALING
    assert stripe.status == Subscription.Status.ACTIVE


@pytest.mark.django_db
def test_subscription_api_exposes_access_and_grace(authenticated_client, organization, starter, settings):
    settings.BILLING_GRACE_DAYS = 3
    subscription = _subscription(organization, starter, Subscription.Status.PAST_DUE, ends_in=-timedelta(days=1))

    data = authenticated_client.get("/api/billing/subscription/").data

    assert data["has_access"] is True
    expected_until = subscription.current_period_end + timedelta(days=3)
    assert abs(timezone.datetime.fromisoformat(data["access_until"]) - expected_until) < timedelta(seconds=1)
    assert data["seats_used"] == 1 and data["seats_limit"] == 3


# --------------------------------------------------------------------------- prolongation


@pytest.mark.django_db
def test_extension_starts_from_the_end_of_a_running_period(starter, pro):
    subscription = _subscription(OrganizationFactory(), starter, ends_in=timedelta(days=10), metadata={"pending_plan_code": "pro"})
    start, end = subscription.current_period_start, subscription.current_period_end

    SubscriptionService.extend(subscription=subscription, months=3, plan=pro, provider=Subscription.Provider.MANUAL)

    subscription.refresh_from_db()
    assert subscription.current_period_end == add_months(end, 3)
    assert subscription.current_period_start == start  # la période en cours continue
    assert subscription.plan == pro and "pending_plan_code" not in subscription.metadata
    assert subscription.provider == Subscription.Provider.MANUAL


@pytest.mark.django_db
def test_extension_of_a_lapsed_subscription_starts_now(starter):
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.PAST_DUE, ends_in=-timedelta(days=20))
    before = timezone.now()

    SubscriptionService.extend(subscription=subscription, months=1)

    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.current_period_start >= before
    assert subscription.current_period_end == add_months(subscription.current_period_start, 1)


@pytest.mark.django_db
def test_quota_is_monthly_even_on_a_twelve_month_period(starter):
    org = OrganizationFactory()
    now = timezone.now()
    SubscriptionFactory(
        organization=org, plan=starter, status=Subscription.Status.ACTIVE,
        current_period_start=now - timedelta(days=45), current_period_end=now + timedelta(days=300),
    )
    old = PressReviewJob.objects.create(organization=org, title="Mois précédent")
    PressReviewJob.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=40))
    PressReviewJob.objects.create(organization=org, title="Ce mois-ci")

    assert SubscriptionService.reviews_used(org.subscription) == 1


def test_add_months_clamps_to_the_end_of_the_month():
    moment = timezone.make_aware(timezone.datetime(2026, 1, 31, 10, 0))
    assert add_months(moment, 1).date().isoformat() == "2026-02-28"
    assert add_months(moment, 12).date().isoformat() == "2027-01-31"


# --------------------------------------------------------------------------- admin (équipe)


@pytest.fixture
def admin_browser(db):
    user = UserFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_admin_action_extends_selected_subscriptions_with_the_chosen_plan(admin_browser, starter, pro):
    subscription = _subscription(OrganizationFactory(), starter, Subscription.Status.TRIALING, ends_in=timedelta(days=2))
    trial_end = subscription.current_period_end

    response = admin_browser.post(
        "/admin/billing/subscription/",
        {"action": "extend_3_months", "_selected_action": [str(subscription.pk)], "plan": str(pro.pk), "index": 0},
    )

    assert response.status_code == 302
    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.plan == pro
    assert subscription.current_period_end == add_months(trial_end, 3)


@pytest.mark.django_db
def test_admin_records_a_manual_payment_as_a_paid_numbered_invoice(admin_browser, starter, pro):
    org = OrganizationFactory(name="Groupe Médias Douala")
    subscription = _subscription(org, starter, Subscription.Status.PAST_DUE, ends_in=-timedelta(days=5))
    url = f"/admin/billing/subscription/{subscription.pk}/record-payment/"

    assert admin_browser.get(url).status_code == 200
    response = admin_browser.post(
        url,
        {"plan": str(pro.pk), "months": "12", "amount_ttc": "2146500", "method": "mobile_money",
         "reference": "MP260101.1234", "note": "Payé par Orange Money", "extend": "on"},
    )

    assert response.status_code == 302
    invoice = Invoice.objects.get(organization=org)
    year = timezone.localtime(invoice.created_at).year
    assert invoice.number == f"RDP-{year}-0001"
    assert invoice.status == Invoice.Status.PAID and invoice.provider == Subscription.Provider.MANUAL
    assert invoice.plan == pro and invoice.months == 12
    assert invoice.amount == Decimal("2146500")
    assert invoice.amount_ht + invoice.vat_amount == invoice.amount
    assert invoice.buyer_name == "Groupe Médias Douala"
    subscription.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE and subscription.plan == pro
    assert subscription.current_period_end == invoice.period_end
    assert invoice.period_end == add_months(invoice.period_start, 12)


@pytest.mark.django_db
def test_admin_subscription_list_and_invoice_pages_render(admin_browser, starter):
    subscription = _subscription(OrganizationFactory(), starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)

    assert admin_browser.get("/admin/billing/subscription/?echeance=7d").status_code == 200
    assert admin_browser.get(f"/admin/billing/subscription/{subscription.pk}/change/").status_code == 200
    assert admin_browser.get("/admin/billing/invoice/").status_code == 200
    assert admin_browser.get(f"/admin/billing/invoice/{invoice.pk}/change/").status_code == 200


# --------------------------------------------------------------------------- factures


@pytest.mark.django_db
def test_invoice_numbers_are_sequential_per_year(starter):
    subscription = _subscription(OrganizationFactory(), starter, ends_in=timedelta(days=3))
    first = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625, extend=False)
    second = InvoiceService.create_for_plan(subscription=subscription, plan=starter, provider=Subscription.Provider.MANUAL)
    year = timezone.localtime(first.created_at).year
    assert (first.number, second.number) == (f"RDP-{year}-0001", f"RDP-{year}-0002")


def test_vat_breakdown_from_ht_and_from_ttc(settings):
    settings.BILLING_VAT_RATE = "19.25"
    assert amounts_from_ht(Decimal("150000")) == {
        "amount_ht": Decimal("150000"), "vat_rate": Decimal("19.25"),
        "vat_amount": Decimal("28875"), "amount": Decimal("178875"),
    }
    from_ttc = amounts_from_ttc(Decimal("178875"))
    assert (from_ttc["amount_ht"], from_ttc["vat_amount"]) == (Decimal("150000"), Decimal("28875"))

    settings.BILLING_VAT_RATE = "0"
    assert amounts_from_ttc(Decimal("50000"))["amount_ht"] == Decimal("50000")


@pytest.mark.parametrize(
    "value, words",
    [
        (71, "soixante et onze"),
        (80, "quatre-vingts"),
        (1000, "mille"),
        (59625, "cinquante-neuf mille six cent vingt-cinq"),
        (178875, "cent soixante-dix-huit mille huit cent soixante-quinze"),
        (200000, "deux cent mille"),
        (3000, "trois mille"),
        (2146500, "deux millions cent quarante-six mille cinq cents"),
    ],
)
def test_amount_in_words(value, words):
    assert amount_in_words(value) == words


@pytest.mark.django_db
def test_invoice_survives_the_deletion_of_its_organization(starter):
    org = OrganizationFactory(name="Entreprise Fermée")
    subscription = _subscription(org, starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)

    org.delete()

    invoice.refresh_from_db()
    assert invoice.organization is None and invoice.subscription is None
    assert invoice.buyer_name == "Entreprise Fermée"


@pytest.mark.django_db
def test_invoice_html_has_legal_mentions_and_escapes_customer_data(starter, settings):
    org = OrganizationFactory()
    BillingProfile.objects.create(
        organization=org, legal_name="<script>alert(1)</script> SARL", niu="P0123", rccm="RC/YAO/2025/B/42",
        address="Bastos\nYaoundé",
    )
    subscription = _subscription(org, starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(
        subscription=subscription, months=1, amount_ttc=59625, reference="<img src=x>", method="mobile_money"
    )

    html = build_invoice_html(invoice)

    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; SARL" in html
    assert invoice.number in html
    assert "RC/YAO/2025/B/42" in html and "P0123" in html  # client
    assert settings.BILLING_SELLER_NIU in html and settings.BILLING_SELLER_RCCM in html  # vendeur
    assert "Total HT" in html and "TVA (19,25 %)" in html and "Total TTC" in html
    assert "59 625 FCFA" in html and "50 000 FCFA" in html
    assert "cinquante-neuf mille six cent vingt-cinq francs CFA" in html
    assert "Acquittée le" in html


@pytest.mark.django_db
def test_invoice_without_vat_says_so(starter, settings):
    settings.BILLING_VAT_RATE = "0"
    subscription = _subscription(OrganizationFactory(), starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.create_for_plan(subscription=subscription, plan=starter, provider=Subscription.Provider.MANUAL)

    html = build_invoice_html(invoice)

    assert "TVA non applicable" in html and "Facture proforma" in html
    assert invoice.amount == Decimal("50000")


@pytest.mark.django_db
def test_invoice_pdf_is_served_to_members_and_staff_only(authenticated_client, organization, starter, staff_client):
    subscription = _subscription(organization, starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)
    outsider = UserFactory()
    MembershipFactory(organization=OrganizationFactory(), user=outsider, role=Membership.Role.OWNER)
    url = f"/api/billing/invoices/{invoice.id}/pdf/"

    with mock.patch("apps.billing.views.render_invoice_pdf", return_value=b"%PDF-1.7 factice") as render:
        member = authenticated_client.get(url)
        staff = staff_client.get(url)
        other = _client_for(outsider).get(url)

    assert member.status_code == 200 and member["Content-Type"] == "application/pdf"
    assert member.content.startswith(b"%PDF")
    assert f'filename="{invoice.number}.pdf"' in member["Content-Disposition"]
    assert staff.status_code == 200
    assert other.status_code == 404
    assert render.call_count == 2


@pytest.mark.django_db
def test_invoice_pdf_reports_a_missing_weasyprint_cleanly(authenticated_client, organization, starter):
    subscription = _subscription(organization, starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)

    with mock.patch("apps.billing.views.render_invoice_pdf", side_effect=OSError("gobject-2.0-0")):
        response = authenticated_client.get(f"/api/billing/invoices/{invoice.id}/pdf/")

    assert response.status_code == 503


def _weasyprint_available():
    try:
        import weasyprint  # noqa: F401
    except OSError:
        return False
    return True


@pytest.mark.django_db
@pytest.mark.skipif(not _weasyprint_available(), reason="WeasyPrint sans ses bibliothèques natives sur ce poste")
def test_invoice_pdf_is_a_real_pdf(starter):
    from apps.billing.invoice_pdf import render_invoice_pdf

    subscription = _subscription(OrganizationFactory(), starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)
    assert render_invoice_pdf(invoice).startswith(b"%PDF")


@pytest.mark.django_db
def test_invoice_list_exposes_number_and_vat_breakdown(authenticated_client, organization, starter):
    subscription = _subscription(organization, starter, ends_in=timedelta(days=3))
    InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)

    item = authenticated_client.get("/api/billing/invoices/").data["results"][0]

    assert item["number"].startswith("RDP-")
    assert item["plan_name"] == "Starter" and item["months"] == 1
    assert Decimal(item["amount_ht"]) == Decimal("50000") and Decimal(item["vat_amount"]) == Decimal("9625")
    assert "proof_file" not in item


# --------------------------------------------------------------------------- prix masqués


@pytest.mark.django_db
def test_prices_are_hidden_from_customers_and_visitors(api_client, authenticated_client, organization, staff_client, starter, pro):
    _subscription(organization, starter, ends_in=timedelta(days=3))

    public = api_client.get("/api/billing/plans/")
    member = authenticated_client.get("/api/billing/plans/")
    staff = staff_client.get("/api/billing/plans/")
    subscription = authenticated_client.get("/api/billing/subscription/")

    assert public.status_code == 200
    for response in (public, member):
        plans = response.data["results"]
        assert [p["code"] for p in plans] == ["starter", "pro"]
        assert all(p["price_amount"] is None for p in plans)
        assert plans[1]["max_seats"] == 10 and plans[1]["max_reviews_per_month"] == 40
    assert {p["price_amount"] for p in staff.data["results"]} == {"50000.00", "150000.00"}
    assert subscription.data["plan"]["price_amount"] is None


# --------------------------------------------------------------------------- places (membres)


@pytest.mark.django_db
def test_seats_count_members_and_live_invitations(organization, starter):
    _subscription(organization, starter, ends_in=timedelta(days=3))  # 3 places
    MembershipFactory(organization=organization)
    live = Invitation.objects.create(organization=organization, email="a@example.com")
    Invitation.objects.create(
        organization=organization, email="b@example.com", expires_at=timezone.now() - timedelta(days=1)
    )

    assert seats_used(organization) == 3  # owner + membre + invitation valable
    assert seats_available(organization) == 0
    assert seats_available(organization, exclude_invitation=live) == 1


@pytest.mark.django_db
def test_seats_are_unlimited_without_subscription(organization):
    assert seats_available(organization) is None


# --------------------------------------------------------------------------- résiliation


@pytest.mark.django_db
def test_cancelling_keeps_the_paid_period_and_can_be_undone(authenticated_client, organization, starter):
    subscription = _subscription(organization, starter, ends_in=timedelta(days=12), provider=Subscription.Provider.MANUAL)

    response = authenticated_client.post("/api/billing/subscription/cancel/")

    assert response.status_code == 200
    assert response.data["status"] == "active" and response.data["cancel_at_period_end"] is True
    assert response.data["has_access"] is True

    response = authenticated_client.post("/api/billing/subscription/resume/")
    assert response.status_code == 200 and response.data["cancel_at_period_end"] is False
    subscription.refresh_from_db()
    assert subscription.cancel_at_period_end is False


@pytest.mark.django_db
def test_cancelling_a_trial_ends_it_immediately(authenticated_client, organization, starter):
    _subscription(organization, starter, Subscription.Status.TRIALING, ends_in=timedelta(days=4))

    response = authenticated_client.post("/api/billing/subscription/cancel/")

    assert response.data["status"] == "canceled" and response.data["has_access"] is False


@pytest.mark.django_db
def test_a_plain_member_cannot_cancel(api_client, organization, starter):
    _subscription(organization, starter, ends_in=timedelta(days=12))
    member = UserFactory()
    MembershipFactory(organization=organization, user=member, role=Membership.Role.MEMBER)

    assert _client_for(member).post("/api/billing/subscription/cancel/").status_code == 403


# --------------------------------------------------------------------------- informations de facturation


@pytest.mark.django_db
def test_billing_profile_is_editable_by_admins_and_copied_onto_new_invoices(authenticated_client, organization, starter):
    assert authenticated_client.get("/api/billing/profile/").data["legal_name"] == organization.name

    response = authenticated_client.put(
        "/api/billing/profile/",
        {"legal_name": "Presse Plus SARL", "address": "Akwa, Douala", "niu": "M0123", "rccm": "RC/DLA/1",
         "email": "compta@presseplus.cm", "phone": "+237 6 70 00 00 00"},
        format="json",
    )
    assert response.status_code == 200, response.data

    subscription = _subscription(organization, starter, ends_in=timedelta(days=3))
    invoice = InvoiceService.record_manual_payment(subscription=subscription, months=1, amount_ttc=59625)
    assert invoice.buyer_name == "Presse Plus SARL"
    assert invoice.buyer["niu"] == "M0123" and invoice.buyer["rccm"] == "RC/DLA/1"


@pytest.mark.django_db
def test_billing_profile_is_read_only_for_plain_members(organization):
    member = UserFactory()
    MembershipFactory(organization=organization, user=member, role=Membership.Role.MEMBER)
    client = _client_for(member)

    assert client.get("/api/billing/profile/").status_code == 200
    assert client.patch("/api/billing/profile/", {"niu": "X"}, format="json").status_code == 403
