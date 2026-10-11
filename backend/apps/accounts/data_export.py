"""Export des données d'une organisation (droit d'accès / portabilité) : un JSON lisible
avec l'organisation, ses membres, ses revues (notices, points clés) et les métadonnées de
ses factures.

Les montants ne figurent pas dans l'export : les prix ne sont communiqués que sur devis.
Les fichiers (photos, PDF sources, exports) ne sont pas inclus : seuls leurs noms le sont."""
from django.utils import timezone

from .models import Invitation, Membership

EXPORT_FORMAT_VERSION = 1


def _iso(value):
    return value.isoformat() if value else None


def _organization(organization):
    return {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "country": organization.country,
        "default_locale": organization.default_locale,
        "contact_phone": organization.contact_phone,
        "created_at": _iso(organization.created_at),
    }


def _members(organization):
    memberships = Membership.objects.filter(organization=organization).select_related("user").order_by("created_at")
    return [
        {
            "email": m.user.email,
            "full_name": m.user.full_name,
            "role": m.role,
            "member_since": _iso(m.created_at),
        }
        for m in memberships
    ]


def _invitations(organization):
    invitations = Invitation.objects.filter(organization=organization).order_by("-created_at")
    return [
        {
            "email": i.email,
            "role": i.role,
            "status": i.status,
            "created_at": _iso(i.created_at),
            "expires_at": _iso(i.expires_at),
            "accepted_at": _iso(i.accepted_at),
        }
        for i in invitations
    ]


def _categories(organization):
    from apps.press_review.models import DetectionCategory

    return [
        {
            "name": c.name,
            "type": c.type,
            "description": c.description,
            "prompt_hint": c.prompt_hint,
            "keywords": list(c.keywords or []),
            "color": c.color,
            "is_active": c.is_active,
        }
        for c in DetectionCategory.objects.filter(organization=organization)
    ]


def _review(job):
    review = getattr(job, "review", None)
    if review is None:
        return None
    return {
        "summary_markdown": review.summary_markdown,
        "structured": review.structured or None,
        "generated_at": _iso(review.generated_at),
    }


def _reviews(organization):
    from apps.press_review.models import PressReviewJob

    jobs = (
        PressReviewJob.objects.filter(organization=organization)
        .select_related("review", "created_by")
        .prefetch_related("documents", "highlights__category")
        .order_by("-created_at")
    )
    return [
        {
            "id": str(job.id),
            "title": job.title,
            "status": job.status,
            "created_by": job.created_by.email if job.created_by else None,
            "created_at": _iso(job.created_at),
            "completed_at": _iso(job.completed_at),
            "documents": [
                {
                    "original_filename": d.original_filename,
                    "kind": d.kind,
                    "page_count": d.page_count,
                    "created_at": _iso(d.created_at),
                }
                for d in job.documents.all()
            ],
            "review": _review(job),
            "highlights": [
                {
                    "category": h.category.name,
                    "category_type": h.category.type,
                    "excerpt": h.excerpt,
                    "explanation": h.explanation,
                    "confidence": h.confidence,
                    "page_number": h.page_number,
                }
                for h in job.highlights.all()
            ],
        }
        for job in jobs
    ]


def _subscription(organization):
    subscription = getattr(organization, "subscription", None)
    if subscription is None:
        return None
    return {
        "plan": subscription.plan.name,
        "status": subscription.status,
        "current_period_start": _iso(subscription.current_period_start),
        "current_period_end": _iso(subscription.current_period_end),
        "max_reviews_per_month": subscription.plan.max_reviews_per_month,
        "max_seats": subscription.plan.max_seats,
    }


def _invoices(organization):
    from apps.billing.models import Invoice

    return [
        {
            "id": str(i.id),
            "status": i.status,
            "provider": i.provider,
            "period_start": _iso(i.period_start),
            "period_end": _iso(i.period_end),
            "paid_at": _iso(i.paid_at),
            "created_at": _iso(i.created_at),
        }
        for i in Invoice.objects.filter(organization=organization).order_by("-created_at")
    ]


def export_organization_data(organization):
    return {
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": _iso(timezone.now()),
        "organization": _organization(organization),
        "members": _members(organization),
        "invitations": _invitations(organization),
        "detection_categories": _categories(organization),
        "reviews": _reviews(organization),
        "subscription": _subscription(organization),
        "invoices": _invoices(organization),
    }


def export_filename(organization):
    return f"revue-de-presse-{organization.slug or 'organisation'}-{timezone.localdate():%Y-%m-%d}.json"
