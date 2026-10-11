"""Logique métier de accounts : les vues appellent ces fonctions, jamais l'inverse
(pas de logique de création/transition dans les serializers ou les vues)."""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import Invitation, Membership, Organization, User, default_invitation_expiry
from .phone import normalize_phone_number

logger = logging.getLogger(__name__)

# Version des CGU/CGV + politique de confidentialité si TERMS_VERSION n'est pas réglé.
DEFAULT_TERMS_VERSION = "2026-10"

SEATS_FULL_MESSAGE = (
    "Toutes les places de votre formule sont occupées ({used} / {limit}, invitations en attente "
    "comprises). Retirez un membre ou annulez une invitation, ou contactez-nous sur WhatsApp pour "
    "ajouter des places."
)
SEATS_FULL_ON_ACCEPT_MESSAGE = (
    "L'organisation {name} a atteint le nombre de places de sa formule ({limit}). Demandez à son "
    "administrateur de libérer une place ou de contacter l'équipe Revue de Presse."
)
TRIAL_ALREADY_USED_MESSAGE = (
    "Ce numéro WhatsApp a déjà bénéficié d'un essai gratuit : votre espace est créé, mais sans essai. "
    "Contactez-nous sur WhatsApp pour activer votre abonnement."
)
TRIAL_UNAVAILABLE_MESSAGE = (
    "Aucun essai gratuit n'a pu être démarré pour votre espace. Contactez-nous sur WhatsApp pour "
    "activer votre abonnement."
)
INVALID_RESET_LINK_MESSAGE = "Ce lien de réinitialisation est invalide ou a expiré. Demandez-en un nouveau."
LAST_OWNER_LEAVE_MESSAGE = (
    "Vous êtes le dernier propriétaire : transférez la propriété à un autre membre (page Équipe) "
    "avant de quitter l'organisation, ou fermez l'organisation."
)


class MembershipPermissionError(Exception):
    """Action refusée par la hiérarchie des rôles (traduite en 403 par les vues)."""


def frontend_url(path):
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}{path}"


def current_terms_version():
    return getattr(settings, "TERMS_VERSION", "") or DEFAULT_TERMS_VERSION


def _terms_fields(accept_terms):
    if not accept_terms:
        return {}
    return {"accepted_terms_at": timezone.now(), "terms_version": current_terms_version()}


# --- Rôles ------------------------------------------------------------------------------


def role_of(organization, user):
    """Rôle de `user` dans `organization`, ou None s'il n'en est pas membre."""
    if user is None or not getattr(user, "pk", None):
        return None
    return (
        Membership.objects.filter(organization=organization, user=user).values_list("role", flat=True).first()
    )


def can_manage_role(actor_role, target_role):
    """Un owner gère tout le monde (owners et admins compris) ; un admin, les membres seulement."""
    if actor_role == Membership.Role.OWNER:
        return True
    return actor_role == Membership.Role.ADMIN and target_role == Membership.Role.MEMBER


def _ensure_can_manage(actor_role, target_role, forbidden_action):
    if can_manage_role(actor_role, target_role):
        return
    if actor_role == Membership.Role.ADMIN:
        raise MembershipPermissionError(f"Seul un propriétaire peut {forbidden_action}.")
    raise MembershipPermissionError("Rôle propriétaire ou administrateur requis dans cette organisation.")


def _ensure_another_owner(organization, membership, message):
    others = Membership.objects.filter(organization=organization, role=Membership.Role.OWNER).exclude(
        id=membership.id
    )
    if not others.exists():
        raise ValueError(message)


# --- Places (formule) -------------------------------------------------------------------


def seat_usage(organization):
    """Places occupées : membres + invitations en attente encore valides (une invitation
    réserve une place jusqu'à son acceptation, son annulation ou son expiration). `limit` est
    None si l'organisation n'a pas encore d'abonnement."""
    members = Membership.objects.filter(organization=organization).count()
    pending = Invitation.objects.filter(
        organization=organization, status=Invitation.Status.PENDING, expires_at__gt=timezone.now()
    ).count()
    subscription = getattr(organization, "subscription", None)
    limit = subscription.plan.max_seats if subscription is not None else None
    used = members + pending
    return {
        "members": members,
        "pending_invitations": pending,
        "used": used,
        "limit": limit,
        "available": None if limit is None else max(0, limit - used),
    }


def seats_available(organization, *, exclude_invitation=None):
    """Places encore libres selon la formule (jamais négatif), None sans abonnement : une
    seule règle, celle de la facturation (`exclude_invitation` évite qu'une invitation
    acceptée se bloque elle-même)."""
    from apps.billing.services import seats_available as billing_seats_available

    return billing_seats_available(organization, exclude_invitation=exclude_invitation)


def _ensure_seat_for_invitation(organization):
    if seats_available(organization) == 0:
        usage = seat_usage(organization)
        raise ValueError(SEATS_FULL_MESSAGE.format(used=usage["used"], limit=usage["limit"]))


def _ensure_seat_for_new_member(invitation):
    """À l'acceptation, l'invitation acceptée garde sa place réservée : refuse seulement si la
    formule n'a plus de place pour elle (formule réduite depuis l'invitation…)."""
    organization = invitation.organization
    if seats_available(organization, exclude_invitation=invitation) == 0:
        limit = seat_usage(organization)["limit"]
        raise ValueError(SEATS_FULL_ON_ACCEPT_MESSAGE.format(name=organization.name, limit=limit))


# --- Inscription et invitations -----------------------------------------------------------


def _send_invitation_email(invitation):
    accept_url = frontend_url(f"/invitations/{invitation.token}/accept")
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


def phone_trial_already_used(phone):
    """Un seul essai gratuit par numéro WhatsApp : le numéro est-il déjà celui d'une autre
    organisation (même fermée) ?"""
    return bool(phone) and Organization.objects.filter(contact_phone=phone).exists()


@transaction.atomic
def register_organization_owner(
    *, email, password, full_name, organization_name, phone_number="", accept_terms=False
):
    """Crée le premier utilisateur d'une entreprise cliente + son organisation, et le
    place owner. C'est le seul chemin qui crée une Organization sans invitation.

    L'essai gratuit n'est offert qu'une fois par numéro WhatsApp (le staff peut toujours
    l'accorder à la main depuis l'admin)."""
    # Import tardif : billing dépend des modèles de accounts.
    from apps.billing.services import SubscriptionService

    phone = normalize_phone_number(phone_number) if phone_number else ""
    trial_already_used = phone_trial_already_used(phone)

    user = User.objects.create_user(
        email=email, password=password, full_name=full_name, **_terms_fields(accept_terms)
    )
    organization = Organization.objects.create(name=organization_name, created_by=user, contact_phone=phone)
    membership = Membership.objects.create(organization=organization, user=user, role=Membership.Role.OWNER)
    if trial_already_used:
        logger.info("Pas d'essai gratuit pour %s : le numéro %s en a déjà bénéficié.", organization, phone)
    else:
        # Essai gratuit : la nouvelle entreprise peut lancer ses premières revues tout de suite.
        SubscriptionService.start_trial(organization=organization)
    return user, organization, membership


def trial_refusal_message(organization):
    """Message à afficher après l'inscription si aucun essai n'a été démarré, sinon None."""
    if getattr(organization, "subscription", None) is not None:
        return None
    if organization.contact_phone and (
        Organization.objects.filter(contact_phone=organization.contact_phone).exclude(pk=organization.pk).exists()
    ):
        return TRIAL_ALREADY_USED_MESSAGE
    return TRIAL_UNAVAILABLE_MESSAGE


@transaction.atomic
def create_invitation(*, organization, email, role, invited_by):
    email = email.strip().lower()
    _ensure_can_manage(
        role_of(organization, invited_by), role, "inviter un administrateur ou un propriétaire"
    )
    # Verrou sur l'organisation : deux invitations simultanées ne dépassent pas la formule.
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if Membership.objects.filter(organization=organization, user__email__iexact=email).exists():
        raise ValueError("Cette personne est déjà membre de l'organisation.")

    already_holds_a_seat = Invitation.objects.filter(
        organization=organization, email=email, status=Invitation.Status.PENDING, expires_at__gt=timezone.now()
    ).exists()
    if not already_holds_a_seat:
        _ensure_seat_for_invitation(organization)

    # Réinviter quelqu'un renouvelle son invitation (nouveau délai de 7 jours).
    invitation, _created = Invitation.objects.update_or_create(
        organization=organization,
        email=email,
        status=Invitation.Status.PENDING,
        defaults={"role": role, "invited_by": invited_by, "expires_at": default_invitation_expiry()},
    )
    transaction.on_commit(lambda: _send_invitation_email(invitation))
    return invitation


def _pending_invitation_for_update(token):
    try:
        invitation = (
            Invitation.objects.select_for_update()
            .select_related("organization")
            .get(token=token, status=Invitation.Status.PENDING, organization__closed_at__isnull=True)
        )
    except Invitation.DoesNotExist as exc:
        raise ValueError("Invitation introuvable ou déjà traitée.") from exc
    if invitation.is_expired:
        raise ValueError("Cette invitation a expiré.")
    return invitation


def _mark_accepted(invitation):
    invitation.status = Invitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at", "updated_at"])


@transaction.atomic
def accept_invitation(*, token, user):
    invitation = _pending_invitation_for_update(token)
    if invitation.email.lower() != user.email.lower():
        raise ValueError("Cette invitation a été envoyée à une autre adresse email.")

    organization = invitation.organization
    if not Membership.objects.filter(organization=organization, user=user).exists():
        _ensure_seat_for_new_member(invitation)
    membership, _created = Membership.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={"role": invitation.role},
    )
    _mark_accepted(invitation)
    return membership


@transaction.atomic
def register_invited_member(*, token, password, full_name, accept_terms=False):
    """Crée un compte pour une personne invitée qui n'a pas encore de compte (à la
    différence de register_organization_owner, ne crée jamais de nouvelle Organization —
    l'utilisateur rejoint directement celle de l'invitation)."""
    invitation = _pending_invitation_for_update(token)
    if User.objects.filter(email__iexact=invitation.email).exists():
        raise ValueError("Un compte existe déjà avec cet email — connectez-vous puis acceptez l'invitation.")
    _ensure_seat_for_new_member(invitation)

    user = User.objects.create_user(
        email=invitation.email, password=password, full_name=full_name, **_terms_fields(accept_terms)
    )
    membership = Membership.objects.create(organization=invitation.organization, user=user, role=invitation.role)
    _mark_accepted(invitation)
    return user, membership


@transaction.atomic
def revoke_invitation(*, organization, invitation_id, requested_by):
    invitation = Invitation.objects.select_for_update().get(
        organization=organization, id=invitation_id, status=Invitation.Status.PENDING
    )
    _ensure_can_manage(
        role_of(organization, requested_by),
        invitation.role,
        "annuler l'invitation d'un administrateur ou d'un propriétaire",
    )
    invitation.status = Invitation.Status.REVOKED
    invitation.save(update_fields=["status", "updated_at"])
    return invitation


# --- Équipe : rôles, retrait, départ, transfert -------------------------------------------


@transaction.atomic
def remove_member(*, organization, membership_id, requested_by):
    membership = Membership.objects.select_for_update().select_related("user").get(
        organization=organization, id=membership_id
    )
    if membership.user_id == requested_by.pk:
        raise ValueError("Pour vous retirer vous-même, utilisez « Quitter l'organisation » dans les paramètres.")
    _ensure_can_manage(
        role_of(organization, requested_by), membership.role, "retirer un administrateur ou un propriétaire"
    )
    if membership.role == Membership.Role.OWNER:
        _ensure_another_owner(
            organization, membership, "Impossible de retirer le dernier propriétaire de l'organisation."
        )
    membership.delete()
    logger.info(
        "Membre %s (%s) retiré de %s par %s.", membership.user.email, membership.role, organization, requested_by
    )


@transaction.atomic
def change_member_role(*, organization, membership_id, role, requested_by):
    membership = Membership.objects.select_for_update().select_related("user").get(
        organization=organization, id=membership_id
    )
    if membership.role == role:
        return membership
    actor_role = role_of(organization, requested_by)
    _ensure_can_manage(actor_role, membership.role, "modifier le rôle d'un administrateur ou d'un propriétaire")
    _ensure_can_manage(actor_role, role, "nommer un administrateur ou un propriétaire")
    if membership.role == Membership.Role.OWNER:
        _ensure_another_owner(
            organization,
            membership,
            "Impossible de retirer son rôle au dernier propriétaire : transférez d'abord la propriété.",
        )
    previous_role = membership.role
    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    logger.info(
        "Rôle de %s dans %s : %s -> %s (par %s).",
        membership.user.email,
        organization,
        previous_role,
        role,
        requested_by,
    )
    return membership


@transaction.atomic
def transfer_ownership(*, organization, membership_id, requested_by):
    """Le propriétaire cède la propriété à un autre membre et devient administrateur."""
    actor = Membership.objects.select_for_update().filter(organization=organization, user=requested_by).first()
    if actor is None or actor.role != Membership.Role.OWNER:
        raise MembershipPermissionError("Seul un propriétaire peut transférer la propriété de l'organisation.")
    target = Membership.objects.select_for_update().select_related("user").get(
        organization=organization, id=membership_id
    )
    if target.pk == actor.pk:
        raise ValueError("Vous êtes déjà propriétaire de l'organisation.")
    target.role = Membership.Role.OWNER
    target.save(update_fields=["role", "updated_at"])
    actor.role = Membership.Role.ADMIN
    actor.save(update_fields=["role", "updated_at"])
    logger.info("Propriété de %s transférée de %s à %s.", organization, requested_by, target.user.email)
    return target


@transaction.atomic
def leave_organization(*, organization, user):
    membership = Membership.objects.select_for_update().get(organization=organization, user=user)
    if membership.role == Membership.Role.OWNER:
        _ensure_another_owner(organization, membership, LAST_OWNER_LEAVE_MESSAGE)
    membership.delete()
    logger.info("%s a quitté %s.", user.email, organization)


def organizations_for(user):
    """Organisations (non fermées) dont l'utilisateur est membre, avec son rôle."""
    return (
        Membership.objects.filter(user=user, organization__closed_at__isnull=True)
        .select_related("organization")
        .order_by("organization__name")
    )


# --- Mot de passe et sessions -------------------------------------------------------------


def revoke_sessions(user):
    """Déconnecte toutes les sessions de l'utilisateur : met en liste noire ses refresh
    tokens connus et refuse tout refresh token émis avant maintenant (y compris ceux issus
    d'une rotation, que simplejwt n'enregistre pas). Les access tokens restent valables
    jusqu'à leur expiration (30 min)."""
    now = timezone.now()
    User.objects.filter(pk=user.pk).update(sessions_revoked_at=now)
    user.sessions_revoked_at = now
    outstanding = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in outstanding], ignore_conflicts=True
    )


def _set_new_password(user, new_password):
    """Valide (AUTH_PASSWORD_VALIDATORS) puis enregistre le mot de passe et ferme les sessions.
    Lève django.core.exceptions.ValidationError si le mot de passe est refusé."""
    validate_password(new_password, user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    revoke_sessions(user)


def password_reset_url(user):
    """Lien à usage unique (PasswordResetTokenGenerator : invalidé par un changement de mot
    de passe ou une connexion, expire après PASSWORD_RESET_TIMEOUT)."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return frontend_url(f"/reinitialiser-mot-de-passe/{uid}/{token}")


def password_reset_expiry():
    return timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)


def _reset_link_validity_label():
    days = max(1, settings.PASSWORD_RESET_TIMEOUT // 86400)
    return f"{days} jour{'s' if days > 1 else ''}"


def _send_password_reset_email(user, reset_url):
    greeting = f"Bonjour {user.full_name}," if user.full_name else "Bonjour,"
    try:
        send_mail(
            subject="Réinitialisation de votre mot de passe Revue de Presse",
            message=(
                f"{greeting}\n\n"
                "Vous avez demandé à réinitialiser votre mot de passe. Ouvrez ce lien pour en choisir "
                f"un nouveau (valable {_reset_link_validity_label()}, utilisable une seule fois) :\n"
                f"{reset_url}\n\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : votre mot de passe "
                "actuel reste valable."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Échec de l'envoi de l'email de réinitialisation à %s", user.email)


def request_password_reset(email):
    """Envoie le lien de réinitialisation si un compte actif correspond. Ne révèle jamais
    (ni par une erreur ni par le code de retour) si l'adresse a un compte."""
    user = User.objects.filter(email__iexact=(email or "").strip(), is_active=True).first()
    if user is None:
        logger.info("Réinitialisation demandée pour une adresse inconnue.")
        return
    _send_password_reset_email(user, password_reset_url(user))


def _user_from_reset_uid(uidb64):
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, DjangoValidationError):
        return None


@transaction.atomic
def confirm_password_reset(*, uidb64, token, new_password):
    user = _user_from_reset_uid(uidb64)
    if user is None or not default_token_generator.check_token(user, token):
        raise ValueError(INVALID_RESET_LINK_MESSAGE)
    _set_new_password(user, new_password)
    logger.info("Mot de passe réinitialisé pour %s.", user.email)
    return user


@transaction.atomic
def change_password(*, user, current_password, new_password):
    if not user.check_password(current_password):
        raise ValueError("Mot de passe actuel incorrect.")
    if current_password == new_password:
        raise ValueError("Le nouveau mot de passe doit être différent de l'actuel.")
    _set_new_password(user, new_password)
    return user


def member_password_reset_link(*, organization, membership_id, requested_by):
    """Lien de réinitialisation à transmettre soi-même (WhatsApp…) quand l'e-mail n'est pas
    configuré, comme pour les invitations. Refusé pour un compte qui a accès à d'autres
    espaces : sinon le propriétaire d'une organisation pourrait prendre la main sur les
    données d'une autre."""
    membership = Membership.objects.select_related("user").get(organization=organization, id=membership_id)
    if membership.user_id == requested_by.pk:
        raise ValueError("Pour votre propre compte, changez votre mot de passe dans Paramètres › Mon compte.")
    _ensure_can_manage(
        role_of(organization, requested_by),
        membership.role,
        "générer un lien de réinitialisation pour un administrateur ou un propriétaire",
    )
    user = membership.user
    if not user.is_active:
        raise ValueError("Ce compte est désactivé.")
    belongs_elsewhere = Membership.objects.filter(user=user).exclude(organization=organization).exists()
    if user.is_staff or user.is_superuser or belongs_elsewhere:
        raise MembershipPermissionError(
            "Ce compte a aussi accès à d'autres espaces : sa réinitialisation passe par l'équipe "
            "Revue de Presse (WhatsApp)."
        )
    logger.info("Lien de réinitialisation généré pour %s par %s (%s).", user.email, requested_by, organization)
    return password_reset_url(user), password_reset_expiry()


# --- Fermeture de l'organisation ----------------------------------------------------------


@transaction.atomic
def close_organization(*, organization, requested_by, confirm_name, reason=""):
    """Fermeture « douce » demandée par un propriétaire : l'organisation devient inaccessible
    à tous ses membres (cf. core.permissions), les invitations en attente sont annulées, et
    les données restent en base jusqu'à leur purge par le staff (admin Django)."""
    organization = Organization.objects.select_for_update().get(pk=organization.pk)
    if role_of(organization, requested_by) != Membership.Role.OWNER:
        raise MembershipPermissionError("Seul un propriétaire peut fermer l'organisation.")
    if organization.is_closed:
        raise ValueError("Cette organisation est déjà fermée.")
    if (confirm_name or "").strip().casefold() != organization.name.strip().casefold():
        raise ValueError("Saisissez exactement le nom de l'organisation pour confirmer sa fermeture.")

    organization.closed_at = timezone.now()
    organization.closed_by = requested_by
    organization.closure_reason = (reason or "").strip()[:2000]
    organization.save(update_fields=["closed_at", "closed_by", "closure_reason", "updated_at"])
    Invitation.objects.filter(organization=organization, status=Invitation.Status.PENDING).update(
        status=Invitation.Status.REVOKED
    )
    logger.warning("Organisation %s (%s) fermée par %s.", organization, organization.pk, requested_by)
    return organization
