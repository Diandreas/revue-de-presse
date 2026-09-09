from datetime import timedelta

import pytest
from django.utils import timezone

from apps.billing.models import Subscription
from apps.billing.services import SubscriptionService
from apps.press_review.models import PressReviewJob
from tests.factories import OrganizationFactory, PlanFactory, SubscriptionFactory


@pytest.mark.django_db
def test_no_quota_without_subscription():
    org = OrganizationFactory()
    assert SubscriptionService.has_quota_for_new_review(organization=org) is False


@pytest.mark.django_db
def test_no_quota_when_subscription_not_active():
    org = OrganizationFactory()
    SubscriptionFactory(organization=org, status=Subscription.Status.PAST_DUE)
    assert SubscriptionService.has_quota_for_new_review(organization=org) is False


@pytest.mark.django_db
def test_quota_respects_plan_limit():
    org = OrganizationFactory()
    plan = PlanFactory(max_reviews_per_month=1)
    SubscriptionFactory(
        organization=org,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=timezone.now() - timedelta(days=1),
    )

    assert SubscriptionService.has_quota_for_new_review(organization=org) is True

    PressReviewJob.objects.create(organization=org, title="Job 1")

    assert SubscriptionService.has_quota_for_new_review(organization=org) is False


@pytest.mark.django_db
def test_jobs_from_a_previous_period_do_not_count_against_quota():
    org = OrganizationFactory()
    plan = PlanFactory(max_reviews_per_month=1)
    subscription = SubscriptionFactory(
        organization=org,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        current_period_start=timezone.now(),
    )
    old_job = PressReviewJob.objects.create(organization=org, title="Ancien job")
    PressReviewJob.objects.filter(pk=old_job.pk).update(created_at=timezone.now() - timedelta(days=45))

    assert SubscriptionService.has_quota_for_new_review(organization=org) is True
    assert subscription.current_period_start is not None
