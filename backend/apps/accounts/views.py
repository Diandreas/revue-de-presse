from django.conf import settings
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import IsOrgAdmin, IsOrgMember, OrganizationContextMixin

from .models import Invitation, Membership
from .serializers import (
    AcceptInvitationSerializer,
    InvitationPreviewSerializer,
    InvitationRegisterSerializer,
    InvitationSerializer,
    InviteCreateSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import (
    accept_invitation,
    create_invitation,
    register_invited_member,
    register_organization_owner,
    remove_member,
)


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
        user, organization, _membership = register_organization_owner(**serializer.validated_data)

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "organization": OrganizationSerializer(organization).data,
                "access": str(refresh.access_token),
            },
            status=201,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class CookieTokenObtainPairView(APIView):
    """Login : renvoie l'access token dans le corps, pose le refresh token en cookie httpOnly."""

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
            raise NotFound("Refresh token manquant.")

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
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


class OrganizationMeView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get(self, request):
        return Response(OrganizationSerializer(request.organization).data)

    def patch(self, request):
        if not IsOrgAdmin().has_permission(request, self):
            raise PermissionDenied("Rôle owner ou admin requis.")
        serializer = OrganizationSerializer(request.organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class OrganizationMembersView(OrganizationContextMixin, generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsOrgMember]
    serializer_class = MembershipSerializer

    def get_queryset(self):
        return Membership.objects.filter(organization=self.request.organization).select_related("user")


class OrganizationMemberDetailView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def delete(self, request, membership_id):
        try:
            remove_member(organization=request.organization, membership_id=membership_id, requested_by=request.user)
        except Membership.DoesNotExist as exc:
            raise NotFound() from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(status=204)


class InviteView(OrganizationContextMixin, APIView):
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def post(self, request):
        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invitation = create_invitation(
                organization=request.organization, invited_by=request.user, **serializer.validated_data
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(InvitationSerializer(invitation).data, status=201)


class InvitationDetailView(APIView):
    """Aperçu public d'une invitation (email, rôle, nom de l'organisation), utilisé
    par la page d'acceptation avant que l'utilisateur ne soit authentifié."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related("organization").get(
                token=token, status=Invitation.Status.PENDING
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
        try:
            user, membership = register_invited_member(token=token, **serializer.validated_data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

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
        try:
            membership = accept_invitation(token=token, user=request.user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response(MembershipSerializer(membership).data, status=200)
