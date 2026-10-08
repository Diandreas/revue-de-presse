from django.core.management.base import BaseCommand

from apps.accounts.models import Organization
from apps.billing.services import SubscriptionService


class Command(BaseCommand):
    help = (
        "Offre l'essai gratuit (TRIAL_DAYS) aux organisations qui n'ont encore aucun abonnement — "
        "utile pour les comptes créés avant l'activation de l'essai automatique."
    )

    def handle(self, *args, **options):
        granted = 0
        for organization in Organization.objects.filter(subscription__isnull=True).order_by("created_at"):
            subscription = SubscriptionService.start_trial(organization=organization)
            if subscription is None:
                self.stdout.write(self.style.WARNING(f"Pas d'essai pour {organization.name} (voir les logs)."))
                continue
            granted += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Essai {subscription.plan.name} offert à {organization.name} "
                    f"jusqu'au {subscription.current_period_end:%d/%m/%Y}."
                )
            )
        self.stdout.write(f"{granted} essai(s) offert(s).")
