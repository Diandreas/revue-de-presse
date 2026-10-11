from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import IsOrgAdmin, IsOrgMember, OrganizationContextMixin

from .data_export import export_filename, export_organization_data
from .models import Invitation, Membership
from .permissions import IsOrgOwner
from .serializers import (
    AcceptInvitationSerializer,
    InvitationPreviewSerializer,
    InvitationRegisterSerializer,
    InvitationSerializer,
    InviteCreateSerializer,
    MembershipRoleSerializer,
    MembershipSerializer,
    OrganizationCloseSerializer,
    OrganizationSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SessionTokenRefreshSerializer,
    TransferOwnershipSerializer,
    UserOrganizationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .services import (
    MembershipPermissionError,
    accept_invitation,
    change_member_role,
    change_password,
    close_organization,
    confirm_password_reset,
    create_invitation,
    leave_organization,
    member_password_reset_link,
    organizations_for,
    register_invited_member,
    register_organization_owner,
    remove_member,
    request_password_reset,
    revoke_invitation,
    seat_usage,
    transfer_ownership,
    trial_refusal_message,
)

PASSWORD_RESET_SENT_MESSAGE = (
    "Si un compte existe pour cette adresse, un e-mail avec un lien de réinitialisation vient de "
    "lui être envoyé. Pensez à vérifier vos courriers indésirables."
)
MEMBER_NOT_FOUND_MESSAGE = "Membre introuvable dans cette organisation."


def _run_service(service, *, not_found="Élément introuvable.", **kwargs):
    """Appelle un service de accounts et traduit ses erreurs métier en réponses HTTP claires :
    hiérarchie des rôles -> 403, règle non respectée -> 400, objet absent -> 404."""
    try:
        return service(**kwargs)
    except ObjectDoesNotExist as exc:
        raise NotFound(not_found) from exc
    except MembershipPermissionError as exc:
        raise PermissionDenied(str(exc)) from exc
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _run_password_service(service, **kwargs):
    """Comme _run_service, avec en plus les refus des validateurs de mot de passe
    (AUTH_PASSWORD_VALIDATORS), rattachés au champ `new_password`."""
    try:
        return _run_service(service, **kwargs)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)}) from exc


def _set_refresh_cookie(response, refresh_token):
    max_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(
        settings.REFRESH_TOKEN_COOKIE_NAME,
        str(refresh_token),
        max_age=max_age,
        httponly=True,
        secure=not settings.DEBUG,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
    )


class RegisterView(APIView):
    """Crée le premier utilisateur + l'organisation d'une entreprise cliente."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, organization, _membership = _run_service(register_organization_owner, **serializer.validated_data)

        refresh = RefreshToken.for_user(user)
        trial_notice = trial_refusal_message(organization)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "organization": OrganizationSerializer(organization).data,
                "access": str(refresh.access_token),
                # Essai refusé (numéro WhatsApp déjà utilisé…) : message à afficher, sinon null.
                "trial_granted": trial_notice is None,
                "trial_notice": trial_notice,
            },
            status=201,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class CookieTokenObtainPairView(APIView):
    """Login : renvoie l'access token dans le corps, pose le refresh token en cookie httpOnly.
    L'e-mail est comparé sans tenir compte de la casse (UserManager.get_by_natural_key)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            # Identifiants invalides -> AuthenticationFailed (via .validate()) plutôt
            # qu'une ValidationError de champ ; interceptée explicitement pour renvoyer
            # un vrai 401 (le handler DRF par défaut le rétrograderait en 403 faute
            # d'authenticator sur cette vue publique).
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            return Response({"detail": "Email ou mot de passe incorrect."}, status=status.HTTP_401_UNAUTHORIZED)

        data = dict(serializer.validated_data)
        refresh = data.pop("refresh")

        response = Response({"access": data["access"]}, status=200)
        _set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(APIView):
    """Lit le refresh token depuis le cookie httpOnly (jamais depuis le corps de la requête)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.REFRESH_TOKEN_COOKIE_NAME)
        if not refresh_token:
            # Pas de session : c'est le cas normal de tout visiteur non connecté (le frontend
            # tente une reprise de session à chaque chargement). Une réponse 4xx s'afficherait
            # en erreur rouge dans la console du navigateur à chaque visite.
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = SessionTokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            # simplejwt lève TokenError (pas une exception DRF) pour un refresh token
            # invalide/expiré/blacklisté — non intercepté, ça remonterait en 500 au lieu
            # d'un 401 propre (c'est ce que fait simplejwt.views.TokenRefreshView en
            # interne ; on ne l'utilise pas directement pour pouvoir lire le cookie).
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return Response(
                {"detail": "Session expirée, merci de vous reconnecter."}, status=status.HTTP_401_UNAUTHORIZED
            )
        data = dict(serializer.validated_data)

        response = Response({"access": data["access"]}, status=200)
        new_refresh = data.get("refresh")  # présent si ROTATE_REFRESH_TOKENS
        if new_refresh:
            _set_refresh_cookie(response, new_refresh)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.REFRESH_TOKEN_COOKIE_NAME)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass
        response = Response(status=204)
        response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME, path=settings.REFRESH_TOKEN_COOKIE_PATH)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class PasswordResetRequestView(APIView):
    """« Mot de passe oublié » : répond toujours 200, que l'adresse ait un compte ou non."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(serializer.validated_data["email"])
        return Response({"detail": PASSWORD_RESET_SENT_MESSAGE})


class PasswordResetConfirmView(APIView):
    """Nouveau mot de passe depuis le lien reçu (e-mail, ou lien partagé par un admin)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        _run_password_service(
            confirm_password_reset, uidb64=data["uid"], token=data["token"], new_password=data["new_password"]
        )
        return Response({"detail": "Votre mot de passe a été modifié. Vous pouvez vous connecter."})


class PasswordChangeView(APIView):
    """Changement de mot de passe : ferme toutes les autres sessions et garde celle-ci ouverte
    (nouveau refresh token en cookie, nouvel access token dans le corps)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _run_password_service(change_password, user=request.user, **serializer.validated_data)

        refresh = RefreshToken.for_user(request.user)
        response = Response({"access": str(refresh.access_token)})
        _set_refresh_cookie(response, str(refresh))
        return response


class OrganizationListView(APIView):
    """Organisations de l'utilisateur (sélecteur) : le frontend envoie ensuite l'en-tête
    X-Organization-Id de celle choisie."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserOrganizationSerializer(organizations_for(request.user), many=True).data)


class OrganizationMeView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    @staticmethod
    def _with_my_role(request, data):
        # Le rôle de l'utilisateur courant permet au frontend de masquer les actions qui lui
        # seraient refusées (inviter, modifier les catégories, payer…) au lieu d'un 403.
        role = (
            Membership.objects.filter(organization=request.organization, user=request.user)
            .values_list("role", flat=True)
            .first()
        )
        return {**data, "my_role": role}

    def get(self, request):
        return Response(self._with_my_role(request, OrganizationSerializer(request.organization).data))

    def patch(self, request):
        if not IsOrgAdmin().has_permission(request, self):
            raise PermissionDenied("Rôle owner ou admin requis.")
        serializer = OrganizationSerializer(request.organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._with_my_role(request, serializer.data))


class OrganizationMembersView(OrganizationContextMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = MembershipSerializer

    def get_queryset(self):
        return Membership.objects.filter(organization=self.request.organization).select_related("user")


class OrganizationSeatsView(OrganizationContextMixin, APIView):
    """Places de la formule : membres + invitations en attente, sur le maximum de la formule."""

    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request):
        return Response(seat_usage(request.organization))


class OrganizationMemberDetailView(OrganizationContextMixin, APIView):
    """Rôle d'un membre (PATCH) et retrait (DELETE). Un admin ne gère que les membres ;
    seul un owner gère les owners et les admins (cf. services.can_manage_role)."""

    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def patch(self, request, membership_id):
        serializer = MembershipRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = _run_service(
            change_member_role,
            not_found=MEMBER_NOT_FOUND_MESSAGE,
            organization=request.organization,
            membership_id=membership_id,
            role=serializer.validated_data["role"],
            requested_by=request.user,
        )
        return Response(MembershipSerializer(membership).data)

    def delete(self, request, membership_id):
        _run_service(
            remove_member,
            not_found=MEMBER_NOT_FOUND_MESSAGE,
            organization=request.organization,
            membership_id=membership_id,
            requested_by=request.user,
        )
        return Response(status=204)


class MemberPasswordResetLinkView(OrganizationContextMixin, APIView):
    """Lien de réinitialisation du mot de passe d'un membre, à lui transmettre (WhatsApp…)
    tant que l'e-mail n'est pas configuré — comme les liens d'invitation."""

    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request, membership_id):
        reset_url, expires_at = _run_service(
            member_password_reset_link,
            not_found=MEMBER_NOT_FOUND_MESSAGE,
            organization=request.organization,
            membership_id=membership_id,
            requested_by=request.user,
        )
        return Response({"reset_url": reset_url, "expires_at": expires_at})


class TransferOwnershipView(OrganizationContextMixin, APIView):
    """Le propriétaire cède la propriété à un membre et devient administrateur."""

    permission_classes = [IsAuthenticated, IsOrgOwner]

    def post(self, request):
        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = _run_service(
            transfer_ownership,
            not_found=MEMBER_NOT_FOUND_MESSAGE,
            organization=request.organization,
            membership_id=serializer.validated_data["membership_id"],
            requested_by=request.user,
        )
        return Response(MembershipSerializer(membership).data)


class LeaveOrganizationView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def post(self, request):
        _run_service(leave_organization, organization=request.organization, user=request.user)
        return Response(status=204)


class OrganizationExportView(OrganizationContextMixin, APIView):
    """Export JSON des données de l'organisation (propriétaires uniquement)."""

    permission_classes = [IsAuthenticated, IsOrgOwner]

    def get(self, request):
        organization = request.organization
        return Response(
            export_organization_data(organization),
            headers={"Content-Disposition": f'attachment; filename="{export_filename(organization)}"'},
        )


class OrganizationCloseView(OrganizationContextMixin, APIView):
    """Fermeture de l'organisation par un propriétaire (accès coupé, purge par le staff)."""

    permission_classes = [IsAuthenticated, IsOrgOwner]

    def post(self, request):
        serializer = OrganizationCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _run_service(
            close_organization,
            organization=request.organization,
            requested_by=request.user,
            **serializer.validated_data,
        )
        return Response(
            {
                "detail": "L'organisation est fermée : plus personne n'y a accès. Ses données seront "
                "supprimées par l'équipe Revue de Presse."
            }
        )


class InviteView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = _run_service(
            create_invitation, organization=request.organization, invited_by=request.user, **serializer.validated_data
        )
        return Response(InvitationSerializer(invitation).data, status=201)


class OrganizationInvitationsView(OrganizationContextMixin, generics.ListAPIView):
    """Invitations en attente, avec leur lien à partager (cf. InvitationSerializer.accept_url)."""

    permission_classes = [IsAuthenticated, IsOrgAdmin]
    serializer_class = InvitationSerializer
    pagination_class = None

    def get_queryset(self):
        return Invitation.objects.filter(
            organization=self.request.organization, status=Invitation.Status.PENDING
        ).order_by("-created_at")


class OrganizationInvitationDetailView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def delete(self, request, invitation_id):
        _run_service(
            revoke_invitation,
            not_found="Invitation introuvable ou déjà traitée.",
            organization=request.organization,
            invitation_id=invitation_id,
            requested_by=request.user,
        )
        return Response(status=204)


class InvitationDetailView(APIView):
    """Aperçu public d'une invitation (email, rôle, nom de l'organisation), utilisé
    par la page d'acceptation avant que l'utilisateur ne soit authentifié."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related("organization").get(
                token=token, status=Invitation.Status.PENDING, organization__closed_at__isnull=True
            )
        except Invitation.DoesNotExist as exc:
            raise NotFound("Invitation introuvable ou déjà traitée.") from exc
        if invitation.is_expired:
            raise NotFound("Cette invitation a expiré.")

        data = {
            "email": invitation.email,
            "role": invitation.role,
            "organization_name": invitation.organization.name,
        }
        return Response(InvitationPreviewSerializer(data).data)


class InvitationRegisterView(APIView):
    """Crée un compte pour une personne invitée qui n'en a pas encore, et la fait
    rejoindre directement l'organisation de l'invitation (pas de nouvelle Organization,
    contrairement à /auth/register/)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        serializer = InvitationRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, membership = _run_service(register_invited_member, token=token, **serializer.validated_data)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "membership": MembershipSerializer(membership).data,
                "access": str(refresh.access_token),
            },
            status=201,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class AcceptInvitationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        AcceptInvitationSerializer(data={"token": token}).is_valid(raise_exception=True)
        membership = _run_service(accept_invitation, token=token, user=request.user)
        return Response(MembershipSerializer(membership).data, status=200)
