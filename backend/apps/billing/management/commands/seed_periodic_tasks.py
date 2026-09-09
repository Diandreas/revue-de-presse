from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

TASKS = [
    {
        "name": "Relances mensuelles Mobile Money",
        "task": "apps.billing.tasks.request_monthly_mobile_money_renewals",
        "cron": {"minute": "0", "hour": "7"},
    },
    {
        "name": "Vérification des abonnements en retard",
        "task": "apps.billing.tasks.check_overdue_subscriptions",
        "cron": {"minute": "30", "hour": "7"},
    },
    {
        "name": "Rappels de renouvellement",
        "task": "apps.billing.tasks.send_renewal_reminders",
        "cron": {"minute": "0", "hour": "8"},
    },
]


class Command(BaseCommand):
    help = "Crée les tâches périodiques de facturation par défaut (planning modifiable ensuite via /admin/)."

    def handle(self, *args, **options):
        for entry in TASKS:
            schedule, _ = CrontabSchedule.objects.get_or_create(
                **entry["cron"], defaults={"timezone": "Africa/Douala"}
            )
            _task, created = PeriodicTask.objects.update_or_create(
                name=entry["name"], defaults={"task": entry["task"], "crontab": schedule, "enabled": True}
            )
            verb = "Créée" if created else "Mise à jour"
            self.stdout.write(self.style.SUCCESS(f"{verb} : {entry['name']}"))
