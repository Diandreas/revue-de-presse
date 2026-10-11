import uuid

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission


class OrganizationContextMixin:
    """Résout `request.organization` à partir de l'en-tête `X-Organization-Id` (ou de
    l'unique organisation de l'utilisateur si non ambigu) et vérifie l'appartenance.

    Les viewsets de domaine DOIVENT filtrer leur queryset par `self.request.organization`
    et ne jamais faire confiance à un organization_id fourni par le client ailleurs
    (corps de requête, query params)."""

    def initial(self, request, *args, **kwargs):
        # DRF appelle check_permissions() DEPUIS super().initial() : request.organization
        # doit donc être résolu AVANT cet appel, sinon IsOrgMember/IsOrgAdmin ne le
        # voient jamais et refusent tout systématiquement. Accéder à request.user ici
        # déclenche l'authentification (lazy property) ; super().initial() la relira
        # ensuite depuis le cache, donc pas de double authentification réelle.
        request.organization = self._resolve_organization(request)
        super().initial(request, *args, **kwargs)

    @staticmethod
    def _resolve_organization(request):
        from apps.accounts.models import Membership

        if not request.user or not request.user.is_authenticated:
            return None

        # Une organisation fermée par son propriétaire n'est plus accessible à personne.
        memberships = Membership.objects.filter(
            user=request.user, organization__closed_at__isnull=True
        ).select_related("organization")
        org_id = request.headers.get("X-Organization-Id")

        # `code` (en plus de `detail`) : le frontend recharge la liste des organisations de
        # l'utilisateur (GET /api/organizations/) au lieu d'afficher une erreur technique.
        if org_id:
            membership = memberships.filter(organization_id=org_id).first() if _is_uuid(org_id) else None
            if membership is None:
                raise PermissionDenied(
                    {
                        "detail": "Vous n'avez plus accès à cette organisation.",
                        "code": "organization_access_lost",
                    }
                )
            return membership.organization

        count = memberships.count()
        if count == 1:
            return memberships.first().organization
        if count == 0:
            raise NotFound(
                {"detail": "Vous ne faites partie d'aucune organisation active.", "code": "no_organization"}
            )
        raise PermissionDenied(
            {
                "detail": "Vous appartenez à plusieurs organisations : choisissez celle à utiliser.",
                "code": "organization_required",
            }
        )


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


class IsOrgMember(BasePermission):
    """Autorise si le contexte d'organisation a été résolu (voir OrganizationContextMixin)."""

    message = "Aucune organisation valide dans le contexte de la requête."

    def has_permission(self, request, view):
        return getattr(request, "organization", None) is not None


class IsOrgAdmin(BasePermission):
    """Autorise si l'utilisateur est owner/admin de l'organisation résolue."""

    message = "Rôle owner ou admin requis dans cette organisation."

    def has_permission(self, request, view):
        organization = getattr(request, "organization", None)
        if organization is None or not request.user.is_authenticated:
            return False

        from apps.accounts.models import Membership

        return Membership.objects.filter(
            organization=organization,
            user=request.user,
            role__in=[Membership.Role.OWNER, Membership.Role.ADMIN],
        ).exists()
