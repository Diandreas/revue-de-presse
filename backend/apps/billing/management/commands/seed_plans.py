from django.core.management.base import BaseCommand

from apps.billing.models import Plan

# Tarifs indicatifs en XAF — à ajuster par le client avant mise en production.
DEFAULT_PLANS = [
    {"code": "starter", "name": "Starter", "price_amount": 50000, "max_reviews_per_month": 10, "max_seats": 3},
    {"code": "pro", "name": "Pro", "price_amount": 150000, "max_reviews_per_month": 40, "max_seats": 10},
    {"code": "enterprise", "name": "Enterprise", "price_amount": 350000, "max_reviews_per_month": 200, "max_seats": 50},
]


class Command(BaseCommand):
    help = "Crée/actualise les plans d'abonnement par défaut (tarifs indicatifs en XAF)."

    def handle(self, *args, **options):
        for data in DEFAULT_PLANS:
            plan, created = Plan.objects.update_or_create(code=data["code"], defaults=data)
            verb = "Créé" if created else "Mis à jour"
            self.stdout.write(self.style.SUCCESS(f"{verb} : {plan.name}"))
