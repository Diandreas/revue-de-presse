"""Règles de facturation partagées : numérotation séquentielle, ventilation HT / TVA / TTC,
identités légales figées sur la facture, calcul de mois calendaires et montant en lettres.

Les montants des formules (`Plan.price_amount`) sont des prix catalogue HT ; le montant
d'une facture (`Invoice.amount`) est toujours le TTC, c'est-à-dire ce que le client paie."""
import calendar
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

# Devises sans sous-unité : les montants sont arrondis au franc près.
ZERO_DECIMAL_CURRENCIES = {"XAF", "XOF"}


# --------------------------------------------------------------------------- dates


def add_months(moment, months):
    """`moment` + `months` mois calendaires (31 janvier + 1 mois -> 28/29 février)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


# --------------------------------------------------------------------------- montants


def vat_rate():
    """Taux de TVA configuré (en %), 0 si absent ou invalide."""
    raw = str(getattr(settings, "BILLING_VAT_RATE", "0") or "0").replace(",", ".").strip()
    try:
        rate = Decimal(raw)
    except InvalidOperation:
        return Decimal("0")
    return rate if rate > 0 else Decimal("0")


def _quantum(currency):
    return Decimal("1") if (currency or "").upper() in ZERO_DECIMAL_CURRENCIES else Decimal("0.01")


def amounts_from_ht(amount_ht, *, currency="XAF", rate=None):
    """Ventilation à partir d'un montant HT (prix catalogue d'une formule)."""
    rate = vat_rate() if rate is None else Decimal(rate)
    quantum = _quantum(currency)
    ht = Decimal(amount_ht).quantize(quantum, rounding=ROUND_HALF_UP)
    vat = (ht * rate / 100).quantize(quantum, rounding=ROUND_HALF_UP)
    return {"amount_ht": ht, "vat_rate": rate, "vat_amount": vat, "amount": ht + vat}


def amounts_from_ttc(amount_ttc, *, currency="XAF", rate=None):
    """Ventilation à partir d'un montant TTC encaissé (paiement manuel, Stripe, CamPay)."""
    rate = vat_rate() if rate is None else Decimal(rate)
    quantum = _quantum(currency)
    ttc = Decimal(amount_ttc).quantize(quantum, rounding=ROUND_HALF_UP)
    ht = (ttc * 100 / (100 + rate)).quantize(quantum, rounding=ROUND_HALF_UP)
    return {"amount_ht": ht, "vat_rate": rate, "vat_amount": ttc - ht, "amount": ttc}


# --------------------------------------------------------------------------- numérotation


def next_invoice_number(moment=None):
    """Prochain numéro de l'année, ex. RDP-2026-0001. Le compteur est verrouillé (select
    for update) : deux factures simultanées ne peuvent pas recevoir le même numéro."""
    from .models import InvoiceCounter

    year = timezone.localtime(moment or timezone.now()).year
    prefix = getattr(settings, "BILLING_INVOICE_PREFIX", "RDP") or "RDP"
    with transaction.atomic():
        counter, _created = InvoiceCounter.objects.select_for_update().get_or_create(year=year)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
    return f"{prefix}-{year}-{counter.last_number:04d}"


# --------------------------------------------------------------------------- identités


def seller_snapshot():
    return {
        "name": getattr(settings, "BILLING_SELLER_NAME", "") or "Revue de Presse",
        "address": getattr(settings, "BILLING_SELLER_ADDRESS", ""),
        "rccm": getattr(settings, "BILLING_SELLER_RCCM", ""),
        "niu": getattr(settings, "BILLING_SELLER_NIU", ""),
        "email": getattr(settings, "BILLING_SELLER_EMAIL", ""),
        "whatsapp": getattr(settings, "BILLING_CONTACT_WHATSAPP", ""),
    }


def buyer_snapshot(organization):
    from .models import BillingProfile

    profile = BillingProfile.objects.filter(organization=organization).first()
    return {
        "name": (profile.legal_name if profile else "") or organization.name,
        "address": profile.address if profile else "",
        "niu": profile.niu if profile else "",
        "rccm": profile.rccm if profile else "",
        "email": profile.email if profile else "",
        "phone": profile.phone if profile else "",
    }


def prepare_invoice(invoice):
    """Complète une facture avant sa première sauvegarde : numéro, vendeur et client figés,
    ventilation HT / TVA si seul le TTC est connu."""
    if not invoice.number:
        invoice.number = next_invoice_number(invoice.created_at)
    if not invoice.seller:
        invoice.seller = seller_snapshot()
    if not invoice.buyer and invoice.organization_id:
        invoice.buyer = buyer_snapshot(invoice.organization)
    if not invoice.buyer_name:
        invoice.buyer_name = (invoice.buyer or {}).get("name", "")
    if invoice.amount_ht is None and invoice.amount is not None:
        breakdown = amounts_from_ttc(invoice.amount, currency=invoice.currency)
        invoice.amount_ht = breakdown["amount_ht"]
        invoice.vat_rate = breakdown["vat_rate"]
        invoice.vat_amount = breakdown["vat_amount"]
    if invoice.vat_rate is None:
        invoice.vat_rate = vat_rate()


# --------------------------------------------------------------------------- en lettres

_UNITS = (
    "zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
    "onze", "douze", "treize", "quatorze", "quinze", "seize",
)
_TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _below_100(n):
    if n <= 16:
        return _UNITS[n]
    if n < 20:
        return "dix-" + _UNITS[n - 10]
    tens, unit = divmod(n, 10)
    if tens in (7, 9):  # soixante-dix…, quatre-vingt-dix…
        base = "soixante" if tens == 7 else "quatre-vingt"
        rest = 10 + unit
        if tens == 7 and unit == 1:
            return "soixante et onze"
        return f"{base}-{_below_100(rest)}"
    if tens == 8:
        return "quatre-vingts" if unit == 0 else f"quatre-vingt-{_UNITS[unit]}"
    word = _TENS[tens]
    if unit == 0:
        return word
    if unit == 1:
        return f"{word} et un"
    return f"{word}-{_UNITS[unit]}"


def _below_1000(n):
    hundreds, rest = divmod(n, 100)
    if hundreds == 0:
        return _below_100(rest)
    head = "cent" if hundreds == 1 else f"{_UNITS[hundreds]} cent"
    if rest == 0:
        return head if hundreds == 1 else head + "s"
    return f"{head} {_below_100(rest)}"


def amount_in_words(value):
    """Montant entier en toutes lettres (orthographe traditionnelle), ex. 178 875 ->
    « cent soixante-dix-huit mille huit cent soixante-quinze »."""
    n = int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if n == 0:
        return "zéro"
    parts = []
    for size, singular, plural in ((10**9, "milliard", "milliards"), (10**6, "million", "millions")):
        count, n = divmod(n, size)
        if count:
            parts.append(f"{_below_1000(count) if count < 1000 else amount_in_words(count)} {plural if count > 1 else singular}")
    thousands, n = divmod(n, 1000)
    if thousands == 1:
        parts.append("mille")
    elif thousands:
        # « mille » est invariable, et « cents » / « vingts » perdent leur s devant lui.
        words = _below_1000(thousands)
        if words.endswith(("cents", "vingts")):
            words = words[:-1]
        parts.append(f"{words} mille")
    if n:
        parts.append(_below_1000(n))
    return " ".join(parts)
