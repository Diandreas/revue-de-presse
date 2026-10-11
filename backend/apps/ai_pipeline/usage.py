"""Mesure de la consommation d'IA : chaque appel Mistral est journalisé (`AIUsage`) avec
l'organisation, la revue et l'étape qui l'ont déclenché.

Le client Mistral ne connaît ni l'organisation ni la revue : les tâches Celery les
déclarent une fois pour toute l'étape avec `ai_call_context(...)` (variable de contexte),
et `record_ai_call` les relit au moment de l'appel. Hors pipeline (shell, script), l'appel
est quand même journalisé, sans organisation.

L'enregistrement ne doit JAMAIS faire échouer une revue : une erreur d'écriture est
journalisée puis ignorée.
"""
import contextvars
import logging
import re
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .errors import status_code_of

logger = logging.getLogger(__name__)

# Tarifs INDICATIFS en dollars par million de jetons (entrée, sortie), pour estimer le coût
# dans l'admin. À vérifier sur https://mistral.ai/pricing et à surcharger sans redéploiement
# via la variable d'environnement AI_TOKEN_PRICES_USD (JSON : {"modèle": [entrée, sortie]}).
DEFAULT_TOKEN_PRICES_USD = {
    "ministral-3b-latest": (0.04, 0.04),
    "ministral-8b-latest": (0.10, 0.10),
    "ministral-14b-latest": (0.20, 0.20),
    "mistral-small-latest": (0.10, 0.30),
    "mistral-medium-latest": (0.40, 2.00),
    "mistral-large-latest": (0.50, 1.50),
}
_MODEL_VERSION_SUFFIX = re.compile(r"-(latest|\d{4})$")

# Valeurs de AIUsage.Operation (sans importer le modèle au chargement du client Mistral).
OPERATION_JSON = "json"
OPERATION_JSON_REPAIR = "json_repair"
OPERATION_VISION = "vision"


@dataclass(frozen=True)
class AICallContext:
    organization_id: Optional[object] = None
    job_id: Optional[object] = None
    step: str = ""


_current_context = contextvars.ContextVar("ai_call_context", default=AICallContext())


@contextmanager
def ai_call_context(*, organization_id=None, job_id=None, step=""):
    """Rattache les appels IA faits dans le bloc à une organisation / revue / étape (pour le
    limiteur de débit par organisation et pour la mesure du coût)."""
    token = _current_context.set(AICallContext(organization_id=organization_id, job_id=job_id, step=str(step or "")))
    try:
        yield
    finally:
        _current_context.reset(token)


def current_ai_context():
    return _current_context.get()


def _token_count(usage, name):
    value = getattr(usage, name, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(name)
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def record_ai_call(*, model, operation, started, response=None, error=None):
    """Journalise un appel (réussi si `error` est None). `started` = time.monotonic() avant
    l'appel ; les jetons sont lus dans `response.usage` (SDK Mistral), 0 s'ils manquent."""
    if not getattr(settings, "AI_USAGE_TRACKING", True):
        return None
    from .models import AIUsage

    context = current_ai_context()
    usage = getattr(response, "usage", None)
    prompt_tokens = _token_count(usage, "prompt_tokens")
    completion_tokens = _token_count(usage, "completion_tokens")
    total_tokens = _token_count(usage, "total_tokens") or prompt_tokens + completion_tokens
    try:
        with transaction.atomic():  # point de sauvegarde : une erreur ici ne casse pas la transaction appelante
            return AIUsage.objects.create(
                organization_id=context.organization_id,
                job_id=context.job_id,
                step=context.step[:30],
                operation=operation,
                model=str(model or "")[:100],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                duration_ms=max(0, int((time.monotonic() - started) * 1000)),
                succeeded=error is None,
                status_code=status_code_of(error) if error is not None else None,
                error="" if error is None else f"{type(error).__name__}: {error}"[:255],
            )
    except Exception:  # noqa: BLE001 - la mesure ne doit jamais faire échouer une revue
        logger.warning("Appel IA non journalisé (modèle %s).", model, exc_info=True)
        return None


# --------------------------------------------------------------------------- coût


def token_prices():
    prices = dict(DEFAULT_TOKEN_PRICES_USD)
    for model, value in (getattr(settings, "AI_TOKEN_PRICES_USD", None) or {}).items():
        try:
            prices[model] = (float(value[0]), float(value[1]))
        except (TypeError, ValueError, IndexError):
            logger.warning("AI_TOKEN_PRICES_USD : tarif illisible pour %r, ignoré.", model)
    return prices


def price_for(model, prices=None):
    """(entrée, sortie) en $ par million de jetons, ou None si le modèle n'est pas tarifé.
    `ministral-8b-2410` est rapproché de `ministral-8b-latest`."""
    prices = token_prices() if prices is None else prices
    if model in prices:
        return prices[model]
    base = _MODEL_VERSION_SUFFIX.sub("", model or "")
    return prices.get(f"{base}-latest")


def estimate_cost_usd(model, prompt_tokens, completion_tokens, prices=None):
    price = price_for(model, prices)
    if price is None:
        return None
    return (prompt_tokens * price[0] + completion_tokens * price[1]) / 1_000_000


# --------------------------------------------------------------------------- totaux


def _empty_totals(label):
    return {
        "organization": label, "calls": 0, "failed": 0, "jobs": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "unpriced_models": set(),
    }


def monthly_totals(*, months=12):
    """Consommation par mois puis par organisation (du plus récent au plus ancien) :
    [{"month": date, "rows": [totaux d'une organisation…], "total": totaux du mois}]."""
    from .models import AIUsage

    since = (timezone.localtime() - timedelta(days=31 * max(1, months))).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    base = AIUsage.objects.filter(created_at__gte=since).annotate(month=TruncMonth("created_at"))
    by_model = (
        base.values("month", "organization_id", "organization__name", "model")
        .annotate(
            calls=Count("id"), failed=Count("id", filter=Q(succeeded=False)),
            prompt=Sum("prompt_tokens"), completion=Sum("completion_tokens"),
        )
        .order_by("-month", "organization__name")
    )
    jobs = {
        (row["month"], row["organization_id"]): row["jobs"]
        for row in base.values("month", "organization_id").annotate(jobs=Count("job", distinct=True)).order_by()
    }
    prices = token_prices()
    months_out = OrderedDict()
    for row in by_model:
        month = months_out.setdefault(row["month"], OrderedDict())
        label = row["organization__name"] or "(hors organisation)"
        totals = month.setdefault(row["organization_id"], _empty_totals(label))
        totals["jobs"] = jobs.get((row["month"], row["organization_id"]), 0)
        _add(totals, row, prices)

    result = []
    for month, organizations in months_out.items():
        total = _empty_totals("Total du mois")
        for totals in organizations.values():
            for key in ("calls", "failed", "jobs", "prompt_tokens", "completion_tokens", "cost_usd"):
                total[key] += totals[key]
            total["unpriced_models"] |= totals["unpriced_models"]
        result.append({"month": month, "rows": list(organizations.values()), "total": total})
    return result


def _add(totals, row, prices):
    prompt, completion = row["prompt"] or 0, row["completion"] or 0
    totals["calls"] += row["calls"]
    totals["failed"] += row["failed"]
    totals["prompt_tokens"] += prompt
    totals["completion_tokens"] += completion
    cost = estimate_cost_usd(row["model"], prompt, completion, prices)
    if cost is None:
        totals["unpriced_models"].add(row["model"])
    else:
        totals["cost_usd"] += cost
