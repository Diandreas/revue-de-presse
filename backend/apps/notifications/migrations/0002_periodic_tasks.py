"""Crée les tâches périodiques de notification et de surveillance (django-celery-beat).

Par migration plutôt que par une commande à lancer à la main : impossible de les oublier
au déploiement. Planning modifiable ensuite dans /admin/django_celery_beat/ (heures
d'Africa/Douala)."""
from django.db import migrations
from django.utils import timezone

TIME_ZONE = "Africa/Douala"

PERIODIC_TASKS = [
    {
        "name": "Supervision : revues bloquées en cours",
        "task": "apps.notifications.tasks.fail_stuck_jobs",
        "interval": {"every": 10, "period": "minutes"},
    },
    {
        "name": "Rappels de fin d'essai (propriétaires)",
        "task": "apps.notifications.tasks.send_trial_ending_reminders",
        "crontab": {"minute": "0", "hour": "9"},
    },
    {
        "name": "Staff : clients à contacter pour le renouvellement",
        "task": "apps.notifications.tasks.send_staff_renewal_digest",
        "crontab": {"minute": "30", "hour": "8"},
    },
]


def create_periodic_tasks(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTasks = apps.get_model("django_celery_beat", "PeriodicTasks")

    for entry in PERIODIC_TASKS:
        schedule = {}
        if "interval" in entry:
            schedule["interval"], _ = IntervalSchedule.objects.get_or_create(**entry["interval"])
        else:
            schedule["crontab"], _ = CrontabSchedule.objects.get_or_create(
                day_of_week="*", day_of_month="*", month_of_year="*", timezone=TIME_ZONE, **entry["crontab"]
            )
        PeriodicTask.objects.get_or_create(
            name=entry["name"], defaults={"task": entry["task"], "enabled": True, **schedule}
        )
    # Prévient un beat déjà démarré que le planning a changé (le modèle historique
    # n'émet pas les signaux qui le font d'habitude).
    PeriodicTasks.objects.update_or_create(ident=1, defaults={"last_update": timezone.now()})


def delete_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name__in=[entry["name"] for entry in PERIODIC_TASKS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("django_celery_beat", "0018_improve_crontab_helptext"),
    ]

    operations = [migrations.RunPython(create_periodic_tasks, delete_periodic_tasks)]
