from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from apps.billing.periodic import ensure_periodic_tasks
from apps.billing.services import billing_is_manual


class Command(BaseCommand):
    help = (
        "Crée / réaligne les tâches périodiques de facturation (déjà faites par la migration "
        "billing 0005 ; planning modifiable ensuite via /admin/). En mode manuel, la relance "
        "Mobile Money est désactivée."
    )

    def handle(self, *args, **options):
        for name, created, enabled in ensure_periodic_tasks(
            CrontabSchedule, PeriodicTask, manual_mode=billing_is_manual()
        ):
            verb = "Créée" if created else "Mise à jour"
            state = "active" if enabled else "désactivée"
            self.stdout.write(self.style.SUCCESS(f"{verb} : {name} ({state})"))
