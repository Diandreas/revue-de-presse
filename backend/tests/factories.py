import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Membership, Organization, User
from apps.billing.models import Plan, Subscription
from apps.press_review.models import DetectionCategory


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = "Test User"

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "testpass1234")
        if create:
            obj.save()


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organisation {n}")


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    organization = factory.SubFactory(OrganizationFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER


class DetectionCategoryFactory(DjangoModelFactory):
    class Meta:
        model = DetectionCategory

    name = factory.Sequence(lambda n: f"Catégorie {n}")
    type = DetectionCategory.Type.IMPORTANT_POINT
    color = "#2563EB"


class PlanFactory(DjangoModelFactory):
    class Meta:
        model = Plan

    code = factory.Sequence(lambda n: f"plan-{n}")
    name = "Pro"
    price_amount = 150000
    max_reviews_per_month = 10
    max_seats = 5


class SubscriptionFactory(DjangoModelFactory):
    class Meta:
        model = Subscription

    organization = factory.SubFactory(OrganizationFactory)
    plan = factory.SubFactory(PlanFactory)
    provider = Subscription.Provider.BANK_TRANSFER
    status = Subscription.Status.ACTIVE
