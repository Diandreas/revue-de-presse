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

        memberships = Membership.objects.filter(user=request.user).select_related("organization")
        org_id = request.headers.get("X-Organization-Id")

        if org_id:
            membership = memberships.filter(organization_id=org_id).first()
            if membership is None:
                raise PermissionDenied("Vous n'êtes pas membre de cette organisation.")
            return membership.organization

        count = memberships.count()
        if count == 1:
            return memberships.first().organization
        if count == 0:
            raise NotFound("Aucune organisation associée à cet utilisateur.")
        raise PermissionDenied(
            "Plusieurs organisations disponibles pour cet utilisateur : "
            "précisez l'en-tête X-Organization-Id."
        )


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
