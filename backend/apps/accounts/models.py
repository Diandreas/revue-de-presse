import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire.")
        # Toujours en minuscules (inscription, invitation, admin, createsuperuser) : la
        # connexion compare sans tenir compte de la casse (cf. get_by_natural_key).
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superuser doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        """Connexion insensible à la casse de l'e-mail : « Jean.Ndjock@… » retrouve le compte
        enregistré en minuscules. Correspondance exacte d'abord (comptes historiques créés
        avec des majuscules), puis sans casse ; deux comptes ne différant que par la casse
        restent ambigus et sont refusés plutôt que de connecter le mauvais."""
        field = self.model.USERNAME_FIELD
        try:
            return self.get(**{field: username})
        except self.model.DoesNotExist:
            pass
        try:
            return self.get(**{f"{field}__iexact": (username or "").strip()})
        except self.model.MultipleObjectsReturned as exc:
            raise self.model.DoesNotExist("Plusieurs comptes ne diffèrent que par la casse.") from exc


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    # Acceptation des CGU/CGV et de la politique de confidentialité (horodatée, versionnée).
    accepted_terms_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=20, blank=True)
    # Changement / réinitialisation du mot de passe : toute session (refresh token) ouverte
    # avant cette date est refusée, y compris les jetons issus d'une rotation que la liste
    # noire de simplejwt ne connaît pas (cf. SessionTokenRefreshSerializer).
    sessions_revoked_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email


class Organization(TimeStampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    country = models.CharField(max_length=2, default="CM")
    default_locale = models.CharField(max_length=5, default="fr")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="organizations_created",
    )
    # Numéro WhatsApp du contact, normalisé (+237…) : relance des essais et un seul essai
    # gratuit par numéro (cf. accounts.services.register_organization_owner).
    contact_phone = models.CharField(max_length=20, blank=True, db_index=True)
    # Fermeture demandée par le propriétaire : l'organisation n'est plus accessible (cf.
    # core.permissions.OrganizationContextMixin) ; le staff purge les données ensuite.
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    closure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    @property
    def is_closed(self):
        return self.closed_at is not None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base = slugify(self.name)[:240] or "organisation"
        slug = base
        suffix = 1
        while Organization.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base}-{suffix}"
        return slug

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Propriétaire"
        ADMIN = "admin", "Administrateur"
        MEMBER = "member", "Membre"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="unique_membership_per_org"),
        ]

    def __str__(self):
        return f"{self.user_id} @ {self.organization_id} ({self.role})"


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)


def generate_invitation_token():
    return uuid.uuid4().hex + uuid.uuid4().hex


class Invitation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Acceptée"
        REVOKED = "revoked", "Révoquée"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=Membership.Role.choices, default=Membership.Role.MEMBER)
    token = models.CharField(max_length=64, unique=True, default=generate_invitation_token)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invitations_sent",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(default=default_invitation_expiry)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=Q(status="pending"),
                name="unique_pending_invitation_per_org_email",
            ),
        ]

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Invitation {self.email} -> {self.organization_id} ({self.status})"
