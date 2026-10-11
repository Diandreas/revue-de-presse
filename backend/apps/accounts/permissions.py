from rest_framework.permissions import BasePermission

from .models import Membership


class IsOrgOwner(BasePermission):
    """Autorise si l'utilisateur est propriétaire de l'organisation résolue (export des
    données, fermeture de l'organisation)."""

    message = "Seul un propriétaire de l'organisation peut effectuer cette action."

    def has_permission(self, request, view):
        organization = getattr(request, "organization", None)
        if organization is None or not request.user.is_authenticated:
            return False
        return Membership.objects.filter(
            organization=organization, user=request.user, role=Membership.Role.OWNER
        ).exists()
