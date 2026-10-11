"""Tâches planifiées de facturation (django-celery-beat). Créées par la migration
0005_periodic_tasks au déploiement, et réalignables à tout moment par
`python manage.py seed_periodic_tasks`. Le planning reste modifiable dans /admin/."""

MOBILE_MONEY_RENEWAL_TASK = "apps.billing.tasks.request_monthly_mobile_money_renewals"

TASKS = [
    {
        "name": "Relances mensuelles Mobile Money",
        "task": MOBILE_MONEY_RENEWAL_TASK,
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


def ensure_periodic_tasks(crontab_model, task_model, *, manual_mode, timezone="Africa/Douala"):
    """Crée ou réaligne les tâches. En mode manuel, la relance Mobile Money est désactivée
    (aucune demande de paiement automatique). Renvoie [(nom, créée ?, activée ?)]."""
    results = []
    for entry in TASKS:
        schedule, _ = crontab_model.objects.get_or_create(
            minute=entry["cron"]["minute"],
            hour=entry["cron"]["hour"],
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            defaults={"timezone": timezone},
        )
        enabled = not (manual_mode and entry["task"] == MOBILE_MONEY_RENEWAL_TASK)
        _task, created = task_model.objects.update_or_create(
            name=entry["name"], defaults={"task": entry["task"], "crontab": schedule, "enabled": enabled}
        )
        results.append((entry["name"], created, enabled))
    return results
