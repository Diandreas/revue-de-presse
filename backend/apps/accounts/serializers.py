from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Invitation, Membership, Organization, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "date_joined"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(max_length=255)
    organization_name = serializers.CharField(max_length=255)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "role", "created_at"]
        read_only_fields = fields


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
