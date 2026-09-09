from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Membership, Organization, User
from apps.billing.models import Plan, Subscription

DEMO_EMAIL = "demo@revue-de-presse.local"
DEMO_PASSWORD = "demo-password-1234"
DEMO_ORG_NAME = "Entreprise Démo"


class Command(BaseCommand):
    help = (
        "Crée un jeu de données de démonstration (organisation, utilisateur, plans, "
        "catégories, abonnement actif) pour tester l'application de bout en bout sans "
        "passer par le formulaire d'inscription."
    )

    def handle(self, *args, **options):
        call_command("seed_default_categories")
        call_command("seed_plans")

        user, user_created = User.objects.get_or_create(
            email=DEMO_EMAIL, defaults={"full_name": "Utilisateur Démo"}
        )
        if user_created:
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=["password"])
            self.stdout.write(self.style.SUCCESS(f"Utilisateur créé : {DEMO_EMAIL} / {DEMO_PASSWORD}"))
        else:
            self.stdout.write(f"Utilisateur déjà existant : {DEMO_EMAIL}")

        organization, org_created = Organization.objects.get_or_create(
            name=DEMO_ORG_NAME, defaults={"created_by": user}
        )
        Membership.objects.get_or_create(
            organization=organization, user=user, defaults={"role": Membership.Role.OWNER}
        )
        verb = "créée" if org_created else "déjà existante"
        self.stdout.write(f"Organisation {verb} : {organization.name}")

        plan = Plan.objects.filter(code="pro").first()
        if plan is not None:
            Subscription.objects.update_or_create(
                organization=organization,
                defaults={
                    "plan": plan,
                    "provider": Subscription.Provider.BANK_TRANSFER,
                    "status": Subscription.Status.ACTIVE,
                    "current_period_start": timezone.now(),
                    "current_period_end": timezone.now() + timedelta(days=30),
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Abonnement actif ({plan.name}) configuré pour {organization.name}."))

        self.stdout.write(self.style.SUCCESS("Données de démonstration prêtes."))
