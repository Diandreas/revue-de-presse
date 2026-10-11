"""Crée les tâches planifiées de facturation au déploiement, au lieu de dépendre de la
commande `seed_periodic_tasks` (jamais documentée, peut-être jamais lancée en prod : un
abonnement payé une fois n'expirait alors jamais). En mode manuel (BILLING_MODE, défaut),
la relance Mobile Money est désactivée. Copie figée de apps.billing.periodic.TASKS."""
from django.conf import settings
from django.db import migrations
from django.utils import timezone

MOBILE_MONEY_RENEWAL_TASK = "apps.billing.tasks.request_monthly_mobile_money_renewals"

TASKS = [
    ("Relances mensuelles Mobile Money", MOBILE_MONEY_RENEWAL_TASK, "0", "7"),
    ("Vérification des abonnements en retard", "apps.billing.tasks.check_overdue_subscriptions", "30", "7"),
    ("Rappels de renouvellement", "apps.billing.tasks.send_renewal_reminders", "0", "8"),
]


def create_tasks(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTasks = apps.get_model("django_celery_beat", "PeriodicTasks")
    manual_mode = getattr(settings, "BILLING_MODE", "manual") != "online"
    for name, task, minute, hour in TASKS:
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            defaults={"timezone": "Africa/Douala"},
        )
        enabled = not (manual_mode and task == MOBILE_MONEY_RENEWAL_TASK)
        PeriodicTask.objects.update_or_create(
            name=name, defaults={"task": task, "crontab": schedule, "enabled": enabled}
        )
    # Les signaux de django-celery-beat ne partent pas depuis une migration : on signale
    # nous-mêmes le changement au planificateur (sinon il garde son ancien planning).
    PeriodicTasks.objects.update_or_create(ident=1, defaults={"last_update": timezone.now()})


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_backfill_invoice_numbers"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(create_tasks, migrations.RunPython.noop),
    ]
