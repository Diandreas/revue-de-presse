"""Facture PDF (WeasyPrint) : proforma tant qu'elle n'est pas réglée, facture acquittée
ensuite. Mentions : numéro, vendeur et client (raison sociale, adresse, RCCM, NIU), période,
HT / TVA / TTC et montant en lettres.

Sécurité (même principe que apps.ai_pipeline.export) : toutes les valeurs sont échappées
— raison sociale et notes viennent du client — et WeasyPrint n'a le droit de charger
aucune ressource (`_deny_all_fetcher`), pour qu'aucun fichier du serveur ne puisse être
embarqué dans le PDF."""
import html
import re
from decimal import Decimal

from django.utils import timezone

from .invoicing import amount_in_words
from .models import Invoice

_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

METHOD_LABELS = {
    "mobile_money": "Mobile Money",
    "bank_transfer": "Virement bancaire",
    "cash": "Espèces",
    "check": "Chèque",
    "other": "Autre",
}

INVOICE_STYLE = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
  @bottom-center { content: "%(footer)s"; font-size: 7.5pt; color: #94a3b8; font-family: %(sans)s; } }
body { font-family: %(sans)s; color: #1e293b; font-size: 10pt; line-height: 1.5; }
table.head { width: 100%%; border-collapse: collapse; border-bottom: 3px solid #0f172a; }
table.head td { padding: 0 0 10pt; vertical-align: bottom; }
.brand { font-size: 16pt; font-weight: bold; color: #0f172a; }
.doc { text-align: right; }
.doc .kind { font-size: 15pt; font-weight: bold; letter-spacing: 1pt; color: #4f46e5; text-transform: uppercase; }
.doc .number { font-size: 11pt; font-weight: bold; margin-top: 2pt; }
.doc .date { color: #64748b; font-size: 9pt; }
table.parties { width: 100%%; border-collapse: separate; border-spacing: 10pt 0; margin: 16pt -10pt; }
table.parties td { width: 50%%; vertical-align: top; }
.party { border: 1px solid #e2e8f0; border-radius: 6pt; padding: 9pt 11pt; }
.party h3 { margin: 0 0 4pt; font-size: 8pt; letter-spacing: 1.5pt; text-transform: uppercase; color: #64748b; }
.party .name { font-weight: bold; font-size: 11pt; color: #0f172a; }
.party p { margin: 1pt 0; font-size: 9pt; }
table.lines { width: 100%%; border-collapse: collapse; margin-top: 6pt; }
table.lines th { background: #0f172a; color: #fff; font-size: 8.5pt; text-align: left; padding: 5pt 7pt; }
table.lines td { border-bottom: 1px solid #e2e8f0; padding: 7pt; vertical-align: top; }
.num { text-align: right; white-space: nowrap; }
table.totals { margin-left: auto; margin-top: 10pt; border-collapse: collapse; min-width: 220pt; }
table.totals td { padding: 4pt 7pt; }
table.totals tr.ttc td { border-top: 2px solid #0f172a; font-weight: bold; font-size: 11.5pt; }
.words { margin-top: 14pt; font-size: 9.5pt; }
.status { margin-top: 14pt; padding: 8pt 11pt; border-radius: 6pt; font-size: 9.5pt; }
.status.paid { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.status.open { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.status.void { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.legal { margin-top: 18pt; font-size: 8pt; color: #64748b; }
"""
SANS_STACK = '"Nimbus Sans", "Helvetica Neue", Helvetica, Arial, "DejaVu Sans", sans-serif'


def _deny_all_fetcher(url, *args, **kwargs):
    raise ValueError(f"Ressource externe refusée dans la facture : {url[:80]}")


def _esc(value):
    return html.escape(str(value or ""))


def _date(moment):
    if not moment:
        return ""
    moment = timezone.localtime(moment)
    return f"{moment.day} {_MONTHS_FR[moment.month - 1]} {moment.year}"


def _money(value, currency):
    value = Decimal(value or 0)
    label = "FCFA" if currency == "XAF" else currency
    decimals = 0 if currency in ("XAF", "XOF") else 2
    formatted = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {label}"


def document_kind(invoice):
    if invoice.status == Invoice.Status.PAID:
        return "Facture"
    if invoice.status == Invoice.Status.REFUNDED:
        return "Facture (remboursée)"
    return "Facture proforma"


def invoice_filename(invoice):
    stem = re.sub(r"[^A-Za-z0-9_-]", "", invoice.number or "") or f"facture-{invoice.id}"
    return f"{stem}.pdf"


def _party(title, data, fallback_name=""):
    data = data or {}
    lines = [f"<div class='name'>{_esc(data.get('name') or fallback_name)}</div>"]
    if data.get("address"):
        lines.append(f"<p>{_esc(data['address']).replace(chr(10), '<br>')}</p>")
    if data.get("rccm"):
        lines.append(f"<p>RCCM : {_esc(data['rccm'])}</p>")
    if data.get("niu"):
        lines.append(f"<p>NIU : {_esc(data['niu'])}</p>")
    for key, label in (("email", "E-mail"), ("phone", "Tél."), ("whatsapp", "WhatsApp")):
        if data.get(key):
            lines.append(f"<p>{label} : {_esc(data[key])}</p>")
    return f"<div class='party'><h3>{title}</h3>{''.join(lines)}</div>"


def _status_block(invoice):
    if invoice.status == Invoice.Status.PAID:
        method = METHOD_LABELS.get((invoice.raw_payload or {}).get("method", ""), invoice.get_provider_display())
        reference = f" — référence {_esc(invoice.provider_reference)}" if invoice.provider_reference else ""
        return (
            f"<div class='status paid'>Acquittée le {_date(invoice.paid_at)} — règlement : "
            f"{_esc(method)}{reference}.</div>"
        )
    if invoice.status in (Invoice.Status.FAILED, Invoice.Status.REFUNDED):
        label = "Annulée" if invoice.status == Invoice.Status.FAILED else "Remboursée"
        return f"<div class='status void'>{label} : cette pièce n'est pas à régler.</div>"
    contact = (invoice.seller or {}).get("whatsapp")
    how = f" Contactez-nous sur WhatsApp ({_esc(contact)})" if contact else " Contactez notre équipe"
    return (
        f"<div class='status open'>À régler.{how} pour convenir du règlement, en rappelant la "
        f"référence {_esc(invoice.number)}.</div>"
    )


def build_invoice_html(invoice):
    currency = invoice.currency
    seller = invoice.seller or {}
    rate = Decimal(invoice.vat_rate or 0)
    amount_ht = invoice.amount_ht if invoice.amount_ht is not None else invoice.amount
    vat_amount = invoice.vat_amount or Decimal("0")
    months = invoice.months or 1
    plan_name = invoice.plan.name if invoice.plan_id else "Abonnement"
    unit_price = Decimal(amount_ht) / months

    description = (
        f"Abonnement Revue de Presse — formule {_esc(plan_name)}<br>"
        f"<span style='color:#64748b;font-size:8.5pt'>Période du {_date(invoice.period_start)} "
        f"au {_date(invoice.period_end)}</span>"
    )
    if rate > 0:
        vat_row = f"<tr><td>TVA ({_esc(f'{rate:g}'.replace('.', ','))} %)</td><td class='num'>{_money(vat_amount, currency)}</td></tr>"
        vat_mention = ""
    else:
        vat_row = "<tr><td>TVA</td><td class='num'>Non applicable</td></tr>"
        vat_mention = "<p>TVA non applicable.</p>"
    words = amount_in_words(invoice.amount)
    currency_words = "francs CFA" if currency in ("XAF", "XOF") else _esc(currency)

    parts = [
        "<table class='head'><tr>",
        f"<td><div class='brand'>{_esc(seller.get('name') or 'Revue de Presse')}</div></td>",
        f"<td class='doc'><div class='kind'>{document_kind(invoice)}</div>",
        f"<div class='number'>N° {_esc(invoice.number)}</div>",
        f"<div class='date'>Émise le {_date(invoice.created_at)}</div></td>",
        "</tr></table>",
        "<table class='parties'><tr>",
        f"<td>{_party('Vendeur', seller, 'Revue de Presse')}</td>",
        f"<td>{_party('Client', invoice.buyer, invoice.buyer_name)}</td>",
        "</tr></table>",
        "<table class='lines'><thead><tr><th>Désignation</th><th class='num'>Quantité</th>",
        "<th class='num'>Prix unitaire HT</th><th class='num'>Total HT</th></tr></thead><tbody>",
        f"<tr><td>{description}</td><td class='num'>{months} mois</td>",
        f"<td class='num'>{_money(unit_price, currency)}</td><td class='num'>{_money(amount_ht, currency)}</td></tr>",
        "</tbody></table>",
        "<table class='totals'>",
        f"<tr><td>Total HT</td><td class='num'>{_money(amount_ht, currency)}</td></tr>",
        vat_row,
        f"<tr class='ttc'><td>Total TTC</td><td class='num'>{_money(invoice.amount, currency)}</td></tr>",
        "</table>",
        f"<p class='words'>Arrêtée la présente facture à la somme de <strong>{words} {currency_words}</strong> TTC.</p>",
        _status_block(invoice),
        f"<div class='legal'>{vat_mention}<p>Document établi par {_esc(seller.get('name') or 'Revue de Presse')}.</p></div>",
    ]
    footer = re.sub(r'["\\\n\r]', "", f"{seller.get('name') or 'Revue de Presse'} · {invoice.number or ''}")
    style = INVOICE_STYLE % {"sans": SANS_STACK, "footer": footer}
    return (
        f"<html lang='fr'><head><meta charset='utf-8'><style>{style}</style></head>"
        f"<body>{''.join(parts)}</body></html>"
    )


def render_invoice_pdf(invoice):
    """Octets du PDF. Import paresseux : WeasyPrint exige des bibliothèques natives
    (Pango/cairo) absentes de certains postes de dev — OSError dans ce cas."""
    from weasyprint import HTML

    return HTML(string=build_invoice_html(invoice), url_fetcher=_deny_all_fetcher).write_pdf()
