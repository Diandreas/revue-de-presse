"""Contrôles de /api/health/ : base de données, Redis (broker Celery) et worker Celery.

Pensé pour un moniteur d'uptime externe appelé toutes les minutes : chaque contrôle a
un délai court, et la réponse du worker (un ping diffusé sur le broker) est mise en cache
quelques secondes pour qu'un appel anonyme répété ne charge pas le broker. Aucun détail
d'erreur n'est renvoyé au client (seulement « ok » / « error ») : il part dans les logs."""
import logging

from django.conf import settings
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)

OK = "ok"
ERROR = "error"
SKIPPED = "skipped"  # non applicable (mode eager, broker sans Redis…)

WORKER_CACHE_KEY = "health:celery-worker"
WORKER_CACHE_SECONDS = 30
WORKER_PING_TIMEOUT = 1.0
REDIS_TIMEOUT = 1.0


def check_database():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return OK


def _redis_broker_url():
    url = settings.CELERY_BROKER_URL or ""
    return url if url.startswith(("redis://", "rediss://")) else None


def check_redis():
    url = _redis_broker_url()
    if url is None:
        return SKIPPED
    import redis

    client = redis.Redis.from_url(url, socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT)
    try:
        client.ping()
    finally:
        client.close()
    return OK


def check_worker():
    if settings.CELERY_TASK_ALWAYS_EAGER or _redis_broker_url() is None:
        return SKIPPED  # pas de worker séparé, ou transport sans diffusion (filesystem://)
    cached = cache.get(WORKER_CACHE_KEY)
    if cached is not None:
        return cached
    from config.celery import app

    # limit=1 : on rend la main dès la première réponse au lieu d'attendre tout le délai.
    replies = app.control.ping(timeout=WORKER_PING_TIMEOUT, limit=1)
    status = OK if replies else ERROR
    cache.set(WORKER_CACHE_KEY, status, WORKER_CACHE_SECONDS)
    return status


CHECKS = ("database", "redis", "worker")  # -> check_database(), check_redis(), check_worker()


def run_checks():
    """{"status": ok|degraded|error, "checks": {...}} — `degraded` = seul le worker manque
    (le site répond mais aucune revue n'avance), `error` = base ou Redis injoignable."""
    results = {}
    for name in CHECKS:
        if name == "worker" and results.get("redis") == ERROR:
            # Broker injoignable : le ping attendrait (voire réessaierait) pour rien.
            results[name] = ERROR
            continue
        try:
            results[name] = globals()[f"check_{name}"]()
        except Exception as exc:
            logger.warning("Contrôle de santé « %s » en échec : %s", name, exc)
            results[name] = ERROR
    if results["database"] == ERROR or results["redis"] == ERROR:
        status = ERROR
    elif results["worker"] == ERROR:
        status = "degraded"
    else:
        status = OK
    return {"status": status, "checks": results}
