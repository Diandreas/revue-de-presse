"""Logique métier de accounts : les vues appellent ces fonctions, jamais l'inverse
(pas de logique de création/transition dans les serializers ou les vues)."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Invitation, Membership, Organization, User

logger = logging.getLogger(__name__)


def _send_invitation_email(invitation):
    accept_url = f"{settings.FRONTEND_BASE_URL}/invitations/{invitation.token}/accept"
    try:
        send_mail(
            subject=f"Invitation à rejoindre {invitation.organization.name} sur Revue de Presse",
            message=(
                f"Vous avez été invité·e à rejoindre {invitation.organization.name}.\n"
                f"Cliquez sur ce lien pour accepter : {accept_url}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Échec de l'envoi de l'email d'invitation à %s", invitation.email)


@transaction.atomic
def register_organization_owner(*, email, password, full_name, organization_name):
    """Crée le premier utilisateur d'une entreprise cliente + son organisation, et le
    place owner. C'est le seul chemin qui crée une Organization sans invitation."""
    user = User.objects.create_user(email=email, password=password, full_name=full_name)
    organization = Organization.objects.create(name=organization_name, created_by=user)
    membership = Membership.objects.create(organization=organization, user=user, role=Membership.Role.OWNER)
    return user, organization, membership


@transaction.atomic
def create_invitation(*, organization, email, role, invited_by):
    email = email.strip().lower()
    if Membership.objects.filter(organization=organization, user__email=email).exists():
        raise ValueError("Cette personne est déjà membre de l'organisation.")

    invitation, _created = Invitation.objects.update_or_create(
        organization=organization,
        email=email,
        status=Invitation.Status.PENDING,
        defaults={"role": role, "invited_by": invited_by},
    )
    transaction.on_commit(lambda: _send_invitation_email(invitation))
    return invitation


@transaction.atomic
def accept_invitation(*, token, user):
    try:
        invitation = Invitation.objects.select_for_update().get(token=token, status=Invitation.Status.PENDING)
    except Invitation.DoesNotExist as exc:
        raise ValueError("Invitation introuvable ou déjà traitée.") from exc

    if invitation.is_expired:
        raise ValueError("Cette invitation a expiré.")
    if invitation.email.lower() != user.email.lower():
        raise ValueError("Cette invitation a été envoyée à une autre adresse email.")

    membership, _created = Membership.objects.get_or_create(
        organization=invitation.organization,
        user=user,
        defaults={"role": invitation.role},
    )
    invitation.status = Invitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at", "updated_at"])
    return membership


@transaction.atomic
def register_invited_member(*, token, password, full_name):
    """Crée un compte pour une personne invitée qui n'a pas encore de compte (à la
    différence de register_organization_owner, ne crée jamais de nouvelle Organization —
    l'utilisateur rejoint directement celle de l'invitation)."""
    try:
        invitation = Invitation.objects.select_for_update().get(token=token, status=Invitation.Status.PENDING)
    except Invitation.DoesNotExist as exc:
        raise ValueError("Invitation introuvable ou déjà traitée.") from exc

    if invitation.is_expired:
        raise ValueError("Cette invitation a expiré.")
    if User.objects.filter(email=invitation.email).exists():
        raise ValueError("Un compte existe déjà avec cet email — connectez-vous puis acceptez l'invitation.")

    user = User.objects.create_user(email=invitation.email, password=password, full_name=full_name)
    membership = Membership.objects.create(organization=invitation.organization, user=user, role=invitation.role)
    invitation.status = Invitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at", "updated_at"])
    return user, membership


@transaction.atomic
def remove_member(*, organization, membership_id, requested_by):
    membership = Membership.objects.select_related("user").get(organization=organization, id=membership_id)
    if membership.role == Membership.Role.OWNER:
        remaining_owners = Membership.objects.filter(
            organization=organization, role=Membership.Role.OWNER
        ).exclude(id=membership.id)
        if not remaining_owners.exists():
            raise ValueError("Impossible de retirer le dernier propriétaire de l'organisation.")
    membership.delete()
