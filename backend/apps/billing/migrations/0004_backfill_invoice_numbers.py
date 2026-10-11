"""Factures existantes : numéro séquentiel par année (ordre de création), identités du
vendeur et du client figées, ventilation HT / TVA à partir du montant TTC."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import migrations
from django.utils import timezone


def _vat_rate():
    raw = str(getattr(settings, "BILLING_VAT_RATE", "0") or "0").replace(",", ".").strip()
    try:
        rate = Decimal(raw)
    except InvalidOperation:
        return Decimal("0")
    return rate if rate > 0 else Decimal("0")


def _seller():
    return {
        "name": getattr(settings, "BILLING_SELLER_NAME", "") or "Revue de Presse",
        "address": getattr(settings, "BILLING_SELLER_ADDRESS", ""),
        "rccm": getattr(settings, "BILLING_SELLER_RCCM", ""),
        "niu": getattr(settings, "BILLING_SELLER_NIU", ""),
        "email": getattr(settings, "BILLING_SELLER_EMAIL", ""),
        "whatsapp": getattr(settings, "BILLING_CONTACT_WHATSAPP", ""),
    }


def backfill(apps, schema_editor):
    Invoice = apps.get_model("billing", "Invoice")
    InvoiceCounter = apps.get_model("billing", "InvoiceCounter")
    prefix = getattr(settings, "BILLING_INVOICE_PREFIX", "RDP") or "RDP"
    rate = _vat_rate()
    seller = _seller()
    for invoice in Invoice.objects.filter(number__isnull=True).select_related("organization").order_by("created_at"):
        year = timezone.localtime(invoice.created_at).year
        counter, _ = InvoiceCounter.objects.get_or_create(year=year)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        invoice.number = f"{prefix}-{year}-{counter.last_number:04d}"
        if not invoice.seller:
            invoice.seller = seller
        if invoice.organization_id and not invoice.buyer_name:
            invoice.buyer_name = invoice.organization.name
            invoice.buyer = invoice.buyer or {"name": invoice.organization.name}
        if invoice.amount_ht is None:
            quantum = Decimal("1") if invoice.currency in ("XAF", "XOF") else Decimal("0.01")
            ttc = Decimal(invoice.amount)
            invoice.amount_ht = (ttc * 100 / (100 + rate)).quantize(quantum, rounding=ROUND_HALF_UP)
            invoice.vat_amount = ttc - invoice.amount_ht
            invoice.vat_rate = rate
        invoice.save()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0003_manual_billing_invoices"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
