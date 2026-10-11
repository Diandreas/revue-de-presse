"""Limiteur de débit des appels au service d'IA, global ET par organisation.

Une seule clé Mistral sert tous les clients : sans limite, une revue de 50 photos peut
consommer tout le débit autorisé et faire échouer les revues des autres entreprises. Avant
chaque appel, `acquire_ai_slot()` réserve une place dans deux compteurs par minute :

- global (`AI_RATE_LIMIT_GLOBAL_PER_MINUTE`) : reste sous la limite du compte Mistral ;
- par organisation (`AI_RATE_LIMIT_ORG_PER_MINUTE`, plus bas) : une grosse revue ne peut
  jamais prendre tout le débit, il reste de la place pour les autres clients.

S'il n'y a plus de place, on attend la minute suivante (au plus
`AI_RATE_LIMIT_MAX_WAIT_SECONDS` au total) ; au-delà, `AIRateLimitBusyError` (traitée comme
un 429) fait relancer l'étape plus tard par Celery au lieu d'occuper un worker.

Les compteurs vivent dans le cache Django (`AI_RATE_LIMIT_CACHE`, « default ») : partagés
entre tous les workers quand ce cache est Redis. Si le cache est injoignable, repli sur un
compteur local au processus (limite alors appliquée par worker). 0 = pas de limite.
"""
import logging
import threading
import time

from django.conf import settings
from django.core.cache import caches

from .errors import AIRateLimitBusyError
from .usage import current_ai_context

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
_KEY_PREFIX = "ai-ratelimit"

_local_lock = threading.Lock()
_local_counters = {}


def _limits(organization_id):
    limits = []
    global_limit = int(getattr(settings, "AI_RATE_LIMIT_GLOBAL_PER_MINUTE", 0) or 0)
    if global_limit > 0:
        limits.append(("global", global_limit))
    org_limit = int(getattr(settings, "AI_RATE_LIMIT_ORG_PER_MINUTE", 0) or 0)
    if org_limit > 0 and organization_id:
        limits.append((f"org:{organization_id}", org_limit))
    return limits


def _local_incr(key, delta=1):
    with _local_lock:
        window = int(key.rsplit(":", 1)[-1])
        for stale in [k for k in _local_counters if int(k.rsplit(":", 1)[-1]) < window]:
            del _local_counters[stale]  # fenêtres passées : la mémoire reste bornée
        _local_counters[key] = _local_counters.get(key, 0) + delta
        return _local_counters[key]


def _incr(key, delta=1):
    """Incrément atomique (Redis) ; repli local si le cache est indisponible."""
    try:
        cache = caches[getattr(settings, "AI_RATE_LIMIT_CACHE", "default")]
        cache.add(key, 0, timeout=WINDOW_SECONDS * 2)
        try:
            return cache.incr(key, delta)
        except ValueError:  # clé expirée entre add() et incr()
            cache.set(key, max(delta, 0), timeout=WINDOW_SECONDS * 2)
            return max(delta, 0)
    except Exception:  # noqa: BLE001 - Redis injoignable : on limite quand même, localement
        logger.warning("Cache du limiteur IA indisponible : compteur local au processus.", exc_info=True)
        return _local_incr(key, delta)


def _try_acquire(limits, now):
    """Réserve une place dans chaque compteur ; renvoie 0, ou le nombre de secondes à
    attendre (fin de la fenêtre courante) si l'un d'eux est plein — rien n'est alors réservé."""
    window = int(now // WINDOW_SECONDS)
    taken = []
    for scope, limit in limits:
        key = f"{_KEY_PREFIX}:{scope}:{window}"
        count = _incr(key)
        taken.append(key)
        if count > limit:
            for reserved in taken:
                _incr(reserved, -1)
            return WINDOW_SECONDS - (now % WINDOW_SECONDS) + 0.05
    return 0


def acquire_ai_slot(*, sleep=time.sleep, clock=time.time):
    """À appeler juste avant chaque appel au service d'IA (cf. MistralClient._chat_complete)."""
    limits = _limits(current_ai_context().organization_id)
    if not limits:
        return
    max_wait = float(getattr(settings, "AI_RATE_LIMIT_MAX_WAIT_SECONDS", 90) or 0)
    waited = 0.0
    while True:
        wait = _try_acquire(limits, clock())
        if wait <= 0:
            return
        if waited + wait > max_wait:
            raise AIRateLimitBusyError(
                f"Limiteur de débit IA saturé ({', '.join(f'{s} {n}/min' for s, n in limits)}) "
                f"après {waited:.0f} s d'attente."
            )
        logger.info("Limiteur de débit IA : attente de %.1f s.", wait)
        sleep(wait)
        waited += wait
