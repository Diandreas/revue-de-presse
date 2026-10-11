"""E-mails transactionnels : revue prête / en échec, alertes au staff, rappels de fin
d'essai, réessais d'envoi. Backend locmem (config.settings.test) : rien ne sort."""
import smtplib
from datetime import timedelta

import pytest
from django.core import mail
from django.db import transaction
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.accounts.models import Membership, Organization
from apps.billing.models import Subscription
from apps.notifications import emails as notification_emails
from apps.notifications import tasks as notification_tasks
from apps.notifications.models import NotificationLog, NotificationPreference
from apps.notifications.services import send_staff_renewal_digest, send_trial_ending_reminders
from apps.press_review.models import PressReviewJob
from apps.press_review.services.pipeline import mark_dispatch_failed, transition_job
from tests.factories import MembershipFactory, OrganizationFactory, PlanFactory, SubscriptionFactory, UserFactory

STAFF = "staff@revue.test"


@pytest.fixture(autouse=True)
def _notification_settings(settings):
    settings.FRONTEND_BASE_URL = "https://app.revue.test"
    settings.ADMIN_BASE_URL = "https://app.revue.test"
    settings.STAFF_NOTIFICATION_EMAILS = [STAFF]
    settings.SUPPORT_WHATSAPP_NUMBER = "+237 693 42 79 13"


def _job_through_drafting(organization, user, title="Revue du lundi"):
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title=title)
    for status in (
        PressReviewJob.Status.TEXT_EXTRACTION,
        PressReviewJob.Status.CHUNKING_SUMMARIZATION,
        PressReviewJob.Status.HIGHLIGHT_DETECTION,
        PressReviewJob.Status.REVIEW_DRAFTING,
    ):
        transition_job(job, status)
    return job


def _sent_to(address):
    return [message for message in mail.outbox if address in message.to]


# --------------------------------------------------------------------------- revue prête / échec


@pytest.mark.django_db
def test_ready_review_emails_its_creator_with_a_link_and_an_html_version(
    organization, user, django_capture_on_commit_callbacks
):
    job = _job_through_drafting(organization, user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        transition_job(job, PressReviewJob.Status.REVIEW_READY)

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [user.email]
    assert "Revue du lundi" in message.subject
    assert f"https://app.revue.test/jobs/{job.pk}" in message.body
    html, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert f"https://app.revue.test/jobs/{job.pk}" in html
    assert "Ouvrir la revue" in html


@pytest.mark.django_db
def test_no_email_is_sent_before_the_transaction_commits(organization, user, django_capture_on_commit_callbacks):
    job = _job_through_drafting(organization, user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        transition_job(job, PressReviewJob.Status.REVIEW_READY)

    assert mail.outbox == []  # un rollback ne doit pas avoir annoncé une revue prête
    assert callbacks


@pytest.mark.django_db
def test_failed_review_emails_the_creator_with_the_reason_and_alerts_the_staff(
    organization, user, django_capture_on_commit_callbacks
):
    job = _job_through_drafting(organization, user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        transition_job(job, PressReviewJob.Status.FAILED, error_message="Le service d'IA est saturé.")

    [to_creator] = _sent_to(user.email)
    assert "Le service d'IA est saturé." in to_creator.body
    assert "Réessayer" in to_creator.body
    assert "+237 693 42 79 13" in to_creator.body
    [to_staff] = _sent_to(STAFF)
    assert organization.name in to_staff.subject
    assert "Rédaction de la revue" in to_staff.body  # étape au moment de l'échec, lisible
    assert f"/admin/press_review/pressreviewjob/{job.pk}/change/" in to_staff.body


@pytest.mark.django_db
def test_dispatch_failure_is_notified_too(organization, user, django_capture_on_commit_callbacks):
    job = PressReviewJob.objects.create(organization=organization, created_by=user, title="Revue")

    with django_capture_on_commit_callbacks(execute=True):
        mark_dispatch_failed(job, "File de tâches indisponible.")

    assert _sent_to(user.email) and _sent_to(STAFF)


@pytest.mark.django_db
def test_opted_out_creator_gets_no_review_email_but_the_staff_still_does(
    organization, user, django_capture_on_commit_callbacks
):
    NotificationPreference.objects.create(user=user, email_review_updates=False)
    job = _job_through_drafting(organization, user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        transition_job(job, PressReviewJob.Status.FAILED, error_message="Panne")

    assert _sent_to(user.email) == []
    assert len(_sent_to(STAFF)) == 1


@pytest.mark.django_db
def test_staff_failure_alerts_can_be_switched_off(organization, user, settings, django_capture_on_commit_callbacks):
    settings.STAFF_NOTIFY_JOB_FAILURES = False
    job = _job_through_drafting(organization, user)
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        transition_job(job, PressReviewJob.Status.FAILED, error_message="Panne")

    assert _sent_to(STAFF) == []
    assert len(_sent_to(user.email)) == 1


@pytest.mark.django_db
def test_intermediate_transitions_send_nothing(organization, user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        _job_through_drafting(organization, user)

    assert mail.outbox == []


@pytest.mark.django_db
def test_job_without_creator_only_alerts_the_staff(organization, django_capture_on_commit_callbacks):
    job = _job_through_drafting(organization, None)

    with django_capture_on_commit_callbacks(execute=True):
        transition_job(job, PressReviewJob.Status.FAILED, error_message="Panne")

    assert [message.to for message in mail.outbox] == [[STAFF]]


@pytest.mark.django_db
def test_html_version_escapes_user_supplied_text(user, django_capture_on_commit_callbacks):
    organization = OrganizationFactory(name="<script>alert(1)</script> SARL")
    Membership.objects.create(organization=organization, user=user, role=Membership.Role.OWNER)
    job = _job_through_drafting(organization, user, title="<b>Revue</b>")
    mail.outbox.clear()

    with django_capture_on_commit_callbacks(execute=True):
        transition_job(job, PressReviewJob.Status.REVIEW_READY)

    html = mail.outbox[0].alternatives[0][0]
    assert "<script>" not in html and "<b>Revue</b>" not in html
    assert "&lt;script&gt;" in html


# --------------------------------------------------------------------------- inscription


@pytest.mark.django_db
def test_new_registration_alerts_the_staff_once_committed(django_capture_on_commit_callbacks):
    owner = UserFactory(email="patron@journal.cm", full_name="Jean Ndjock")
    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():  # comme accounts.services.register_organization_owner
            organization = Organization.objects.create(name="Groupe Médias Douala", created_by=owner)
            Membership.objects.create(organization=organization, user=owner, role=Membership.Role.OWNER)
            SubscriptionFactory(
                organization=organization,
                status=Subscription.Status.TRIALING,
                current_period_end=timezone.now() + timedelta(days=7),
            )

    [message] = _sent_to(STAFF)
    assert "Groupe Médias Douala" in message.subject
    assert "Jean Ndjock <patron@journal.cm>" in message.body
    assert "Essai gratuit jusqu'au" in message.body
    assert f"/admin/accounts/organization/{organization.pk}/change/" in message.body


@pytest.mark.django_db
def test_staff_recipients_fall_back_to_active_superusers(settings, django_capture_on_commit_callbacks):
    settings.STAFF_NOTIFICATION_EMAILS = []
    UserFactory(email="root@revue.test", is_superuser=True, is_staff=True)
    UserFactory(email="ancien@revue.test", is_superuser=True, is_staff=True, is_active=False)

    with django_capture_on_commit_callbacks(execute=True):
        OrganizationFactory(name="Nouvelle SARL")

    assert [message.to for message in mail.outbox] == [["root@revue.test"]]


@pytest.mark.django_db
def test_no_staff_address_at_all_means_no_email_and_no_error(settings, django_capture_on_commit_callbacks):
    settings.STAFF_NOTIFICATION_EMAILS = []

    with django_capture_on_commit_callbacks(execute=True):
        OrganizationFactory(name="Nouvelle SARL")

    assert mail.outbox == []


# --------------------------------------------------------------------------- fin d'essai


def _trial(ends_in, **org_kwargs):
    organization = OrganizationFactory(**org_kwargs)
    owner = UserFactory(full_name="Awa Owner")
    admin = UserFactory()
    member = UserFactory()
    Membership.objects.create(organization=organization, user=owner, role=Membership.Role.OWNER)
    MembershipFactory(organization=organization, user=admin, role=Membership.Role.ADMIN)
    MembershipFactory(organization=organization, user=member, role=Membership.Role.MEMBER)
    subscription = SubscriptionFactory(
        organization=organization,
        plan=PlanFactory(price_amount=150000),
        status=Subscription.Status.TRIALING,
        current_period_end=timezone.now() + ends_in,
    )
    return subscription, owner, admin, member


@pytest.mark.django_db
def test_trial_ending_reminder_reaches_owners_and_admins_with_whatsapp_and_no_price():
    subscription, owner, admin, member = _trial(timedelta(days=1, hours=20), name="Cabinet Ekane")

    sent = send_trial_ending_reminders(now=timezone.now())

    assert sent == 1
    assert sorted(m.to[0] for m in mail.outbox) == sorted([owner.email, admin.email])
    message = _sent_to(owner.email)[0]
    assert "Bonjour Awa Owner," in message.body
    assert "Cabinet Ekane" in message.body
    assert "+237 693 42 79 13" in message.body
    assert "https://wa.me/237693427913?text=" in message.body
    assert "150" not in message.body and "FCFA" not in message.body  # prix masqués : sur devis
    assert _sent_to(member.email) == []


@pytest.mark.django_db
def test_trial_ending_reminder_is_sent_only_once():
    _trial(timedelta(days=1))
    now = timezone.now()

    send_trial_ending_reminders(now=now)
    first = len(mail.outbox)
    send_trial_ending_reminders(now=now + timedelta(hours=6))

    assert first == 2 and len(mail.outbox) == first
    assert NotificationLog.objects.filter(kind="trial_ending").count() == 1


@pytest.mark.django_db
def test_trials_far_from_their_end_or_already_over_get_no_reminder():
    _trial(timedelta(days=5))
    _trial(-timedelta(hours=3))

    assert send_trial_ending_reminders(now=timezone.now()) == 0
    assert mail.outbox == []


# --------------------------------------------------------------------------- récapitulatif staff


@pytest.mark.django_db
def test_staff_digest_lists_the_customers_to_contact_for_renewal():
    now = timezone.now()
    soon = SubscriptionFactory(
        organization=OrganizationFactory(name="Bientôt SA"), current_period_end=now + timedelta(days=3)
    )
    SubscriptionFactory(
        organization=OrganizationFactory(name="Retard SARL"),
        status=Subscription.Status.PAST_DUE,
        current_period_end=now - timedelta(days=2),
    )
    SubscriptionFactory(organization=OrganizationFactory(name="Tranquille SA"), current_period_end=now + timedelta(days=20))
    SubscriptionFactory(
        organization=OrganizationFactory(name="Résiliée SA"),
        status=Subscription.Status.CANCELED,
        current_period_end=now + timedelta(days=1),
    )

    assert send_staff_renewal_digest(now=now) == 2

    [message] = mail.outbox
    assert message.to == [STAFF]
    assert "Bientôt SA" in message.body and "Retard SARL" in message.body
    assert "Tranquille SA" not in message.body and "Résiliée SA" not in message.body
    assert "retard de paiement" in message.body
    assert f"/admin/billing/subscription/{soon.pk}/change/" in message.body
    assert message.body.index("Retard SARL") < message.body.index("Bientôt SA")  # le plus urgent d'abord


@pytest.mark.django_db
def test_staff_digest_is_sent_at_most_once_a_day_and_never_empty():
    now = timezone.now()
    assert send_staff_renewal_digest(now=now) == 0
    assert mail.outbox == []

    SubscriptionFactory(current_period_end=now + timedelta(days=2))
    send_staff_renewal_digest(now=now)
    send_staff_renewal_digest(now=now + timedelta(minutes=5))

    assert len(mail.outbox) == 1


# --------------------------------------------------------------------------- envoi et réessais


class _FakeRequest:
    def __init__(self, retries=0, is_eager=False):
        self.retries = retries
        self.is_eager = is_eager


class _FakeTask:
    max_retries = notification_tasks.EMAIL_MAX_RETRIES

    def __init__(self, **request):
        self.request = _FakeRequest(**request)
        self.retried_with = None

    def retry(self, exc, countdown):
        self.retried_with = countdown
        return RuntimeError("retry")


PAYLOAD = {"to": ["client@exemple.cm"], "subject": "Sujet", "text": "Corps", "html": "<p>Corps</p>", "reply_to": None}


def _smtp_down(**kwargs):
    raise smtplib.SMTPServerDisconnected("connexion perdue")


def test_smtp_failure_schedules_a_retry_with_growing_delay(monkeypatch):
    monkeypatch.setattr(notification_tasks, "deliver_email", _smtp_down)
    task = _FakeTask(retries=2)

    with pytest.raises(RuntimeError, match="retry"):
        notification_tasks.deliver_or_retry(task, PAYLOAD)

    assert task.retried_with == notification_tasks.EMAIL_RETRY_BASE_SECONDS * 4


def test_exhausted_retries_log_an_error_instead_of_failing_silently(monkeypatch, caplog):
    monkeypatch.setattr(notification_tasks, "deliver_email", _smtp_down)
    task = _FakeTask(retries=notification_tasks.EMAIL_MAX_RETRIES)

    assert notification_tasks.deliver_or_retry(task, PAYLOAD) is False
    assert task.retried_with is None
    assert "définitivement non envoyé" in caplog.text


def test_refused_recipient_is_not_retried(monkeypatch):
    def _refused(**kwargs):
        raise smtplib.SMTPRecipientsRefused({"client@exemple.cm": (550, b"unknown")})

    monkeypatch.setattr(notification_tasks, "deliver_email", _refused)
    task = _FakeTask()

    assert notification_tasks.deliver_or_retry(task, PAYLOAD) is False
    assert task.retried_with is None


def test_eager_mode_never_raises_into_the_caller(monkeypatch):
    monkeypatch.setattr(notification_tasks, "deliver_email", _smtp_down)

    assert notification_tasks.send_email.apply(kwargs=PAYLOAD).get() is False


def test_send_email_task_delivers_text_and_html():
    assert notification_tasks.send_email.apply(kwargs=PAYLOAD).get() is True

    [message] = mail.outbox
    assert message.body == "Corps"
    assert message.alternatives[0][0] == "<p>Corps</p>"


def test_unreachable_broker_falls_back_to_a_direct_send(monkeypatch, caplog):
    def _broker_down(**kwargs):
        raise ConnectionError("broker injoignable")

    monkeypatch.setattr(notification_tasks.send_email, "delay", _broker_down)
    email = notification_emails.Email(subject="Test", paragraphs=["Bonjour"])

    assert notification_emails.queue_email(to=["a@exemple.cm"], email=email) is True
    assert [message.to for message in mail.outbox] == [["a@exemple.cm"]]
    assert "envoi direct" in caplog.text


# --------------------------------------------------------------------------- préférences et planning


@pytest.mark.django_db
def test_preferences_endpoint_reads_and_updates_only_the_current_user(authenticated_client, user):
    response = authenticated_client.get("/api/notifications/preferences/")
    assert response.status_code == 200
    assert response.data == {"email_review_updates": True}

    response = authenticated_client.patch(
        "/api/notifications/preferences/", {"email_review_updates": False}, format="json"
    )

    assert response.status_code == 200
    assert NotificationPreference.wants_review_updates(user) is False


@pytest.mark.django_db
def test_preferences_endpoint_requires_authentication(api_client):
    assert api_client.get("/api/notifications/preferences/").status_code == 401


@pytest.mark.django_db
def test_periodic_tasks_are_created_by_migration():
    # On rejoue la migration : un test transactionnel ailleurs dans la suite vide la base
    # (flush), ce qui efface les lignes créées par les migrations de données.
    import importlib

    from django.apps import apps as registry

    migration = importlib.import_module("apps.notifications.migrations.0002_periodic_tasks")
    PeriodicTask.objects.filter(task__startswith="apps.notifications.tasks.").delete()
    migration.create_periodic_tasks(registry, None)

    tasks = dict(PeriodicTask.objects.values_list("task", "enabled"))

    assert tasks.get("apps.notifications.tasks.fail_stuck_jobs") is True
    assert tasks.get("apps.notifications.tasks.send_trial_ending_reminders") is True
    assert tasks.get("apps.notifications.tasks.send_staff_renewal_digest") is True
