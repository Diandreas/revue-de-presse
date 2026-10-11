from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings as jwt_settings

from .models import Invitation, Membership, Organization, User
from .phone import normalize_phone_number

TERMS_REQUIRED_MESSAGE = (
    "Vous devez accepter les conditions générales (CGU/CGV) et la politique de confidentialité "
    "pour créer un compte."
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "date_joined"]
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """« Mon compte » : seul le nom est modifiable (l'e-mail sert d'identifiant)."""

    full_name = serializers.CharField(max_length=255, min_length=2, trim_whitespace=True)

    class Meta:
        model = User
        fields = ["full_name"]


def _validate_terms_accepted(value):
    if value is not True:
        raise serializers.ValidationError(TERMS_REQUIRED_MESSAGE)
    return value


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(max_length=255)
    organization_name = serializers.CharField(max_length=255)
    # Numéro WhatsApp : relance de l'essai, et un seul essai gratuit par numéro.
    phone_number = serializers.CharField(max_length=32)
    accept_terms = serializers.BooleanField()

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value

    def validate_phone_number(self, value):
        try:
            return normalize_phone_number(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_accept_terms(self, value):
        return _validate_terms_accepted(value)


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh qui refuse aussi les sessions fermées par un changement / une réinitialisation
    du mot de passe (User.sessions_revoked_at) et celles d'un compte désactivé."""

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user = User.objects.filter(pk=refresh.get(jwt_settings.USER_ID_CLAIM)).first()
        if user is None or not user.is_active:
            raise TokenError("Compte introuvable ou désactivé.")
        revoked_at = user.sessions_revoked_at
        if revoked_at is not None and refresh.get("iat", 0) < int(revoked_at.timestamp()):
            raise TokenError("Session fermée après un changement de mot de passe.")
        return super().validate(attrs)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "created_at"]
        read_only_fields = fields


class MembershipRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)


class TransferOwnershipSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()


class OrganizationCloseSerializer(serializers.Serializer):
    confirm_name = serializers.CharField(max_length=255)
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class UserOrganizationSerializer(serializers.Serializer):
    """Une organisation de l'utilisateur (sélecteur d'organisation), construite depuis
    sa Membership."""

    id = serializers.UUIDField(source="organization.id")
    name = serializers.CharField(source="organization.name")
    slug = serializers.CharField(source="organization.slug")
    my_role = serializers.CharField(source="role")


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "country", "default_locale", "created_at"]
        read_only_fields = ["id", "slug", "created_at"]


class InvitationSerializer(serializers.ModelSerializer):
    # Lien à transmettre à la personne invitée (WhatsApp, email…) : l'envoi automatique
    # d'email dépend d'un serveur SMTP qui peut ne pas être configuré. Uniquement exposé
    # aux owners/admins (vues d'invitation protégées par IsOrgAdmin).
    accept_url = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "status", "expires_at", "created_at", "accept_url"]
        read_only_fields = ["id", "status", "expires_at", "created_at", "accept_url"]

    def get_accept_url(self, obj):
        return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/invitations/{obj.token}/accept"


class InviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices, default=Membership.Role.MEMBER)


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField()


class InvitationPreviewSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    organization_name = serializers.CharField()


class InvitationRegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    accept_terms = serializers.BooleanField()

    def validate_accept_terms(self, value):
        return _validate_terms_accepted(value)
