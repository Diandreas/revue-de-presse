"""
Settings communs à tous les environnements. Ne jamais mettre de secret en dur ici :
tout passe par des variables d'environnement (voir /.env.example à la racine du repo).
"""
import os
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")
# Chemin de l'administration Django. En production, préférez un chemin difficile à
# deviner (ex. "gestion-7f3k9q/") : `check --deploy` le signale sinon (core.W001).
ADMIN_URL = (env("DJANGO_ADMIN_URL", default="admin/").strip("/") or "admin") + "/"

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_celery_beat",
    "drf_spectacular",
]

# Complétées au fil des phases de build (core, accounts, press_review, ai_pipeline, billing, notifications).
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.press_review",
    "apps.ai_pipeline",
    "apps.billing",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.AdminLoginThrottleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://revue:revue@localhost:5432/revue_de_presse"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# Fichiers clients privés (cf. apps.core.media) : jamais servis en accès libre ; chaque
# URL renvoyée par l'API est un lien signé, lié au fichier, valable MEDIA_URL_MAX_AGE s.
STORAGES = {
    "default": {"BACKEND": "apps.core.media.PrivateMediaStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_URL_MAX_AGE = env.int("MEDIA_URL_MAX_AGE", default=30 * 60)
# True derrière nginx (prod) : Django vérifie la signature puis délègue l'envoi à
# l'emplacement « internal » MEDIA_X_ACCEL_PREFIX (ops/nginx/presse-media.conf).
MEDIA_X_ACCEL_REDIRECT = env.bool("MEDIA_X_ACCEL_REDIRECT", default=False)
MEDIA_X_ACCEL_PREFIX = "/protected-media/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    # Limitation de débit (cf. apps.core.throttling) : globale par IP / par utilisateur,
    # puis par route sensible et par adresse e-mail saisie. Compteurs dans CACHES.
    "DEFAULT_THROTTLE_CLASSES": (
        "apps.core.throttling.AnonRateThrottle",
        "apps.core.throttling.UserRateThrottle",
        "apps.core.throttling.RouteScopedRateThrottle",
        "apps.core.throttling.EmailRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",  # le suivi d'une revue interroge l'API toutes les 2,5 s
        "login": "10/min",
        "login_email": "10/min",
        "register": "5/hour",
        "invitations": "60/hour",
        "password_reset": "10/hour",
        "password_reset_email": "5/hour",
        "uploads": "120/hour",  # une revue = jusqu'à 50 photos
        "jobs": "30/hour",
        "admin_login": "10/min",
    },
    # Nombre de proxys de confiance devant Django (nginx = 1) : l'IP du client est alors lue
    # dans X-Forwarded-For sans pouvoir être falsifiée. Vide = REMOTE_ADDR (dev).
    "NUM_PROXIES": env.int("DJANGO_NUM_PROXIES", default=None),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Revue de Presse API",
    "DESCRIPTION": "API de génération procédurale de revues de presse assistée par IA.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # /api/docs/ et /api/schema/ réservés à l'équipe plateforme (is_staff), connectée à
    # l'admin Django (session) ou avec un jeton. Ouverts à tous en dev (settings/dev.py).
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SERVE_AUTHENTICATION": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
}

# --- Auth ---
AUTH_USER_MODEL = "accounts.User"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Nom + options du cookie httpOnly portant le refresh token (posé par apps.accounts.views).
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/api/auth/"
REFRESH_TOKEN_COOKIE_SAMESITE = "Lax"

# --- CORS (SPA React servie sur un port différent en dev) ---
CORS_ALLOWED_ORIGINS = env.list("DJANGO_CORS_ALLOWED_ORIGINS", default=[FRONTEND_BASE_URL])
CORS_ALLOW_CREDENTIALS = True

# --- Cache (compteurs de la limitation de débit) ---
# Redis en production, partagé par tous les workers ; base dédiée conseillée
# (ex. redis://127.0.0.1:6379/2) pour ne pas cohabiter avec la file Celery.
REDIS_URL = env("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "presse",
            # Redis arrêté : échec rapide, la limitation est alors ignorée (cf. apps.core.throttling).
            "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "presse"}}

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# L'analyse tourne en arrière-plan : si le broker est injoignable, la mise en file doit
# échouer vite (le job est alors marqué FAILED avec un message clair, cf.
# press_review.views._start_pipeline) au lieu de bloquer la requête pendant des minutes.
CELERY_BROKER_CONNECTION_TIMEOUT = 3
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1}
# Une tâche qui pend (OCR d'une image géante, appel réseau bloqué) ne doit pas
# monopoliser un worker indéfiniment. (Ignoré par le pool `solo` de Windows.)
CELERY_TASK_SOFT_TIME_LIMIT = 15 * 60
CELERY_TASK_TIME_LIMIT = 20 * 60
# Une tâche n'est acquittée qu'à la fin : si le worker meurt en plein traitement, elle
# est rejouée (les étapes sont idempotentes) au lieu d'être perdue en silence.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

if CELERY_BROKER_URL.startswith("filesystem://"):
    # Mode « vrai worker sans Redis ni Docker » (dev Windows, démo) : file de tâches sur
    # disque. Lancer : CELERY_BROKER_URL=filesystem:// celery -A config worker -P solo
    _celery_fs_dir = BASE_DIR / ".celery_broker"
    (_celery_fs_dir / "queue").mkdir(parents=True, exist_ok=True)
    (_celery_fs_dir / "control").mkdir(parents=True, exist_ok=True)
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "data_folder_in": str(_celery_fs_dir / "queue"),
        "data_folder_out": str(_celery_fs_dir / "queue"),
        "control_folder": str(_celery_fs_dir / "control"),
    }
    CELERY_RESULT_BACKEND = "cache+memory://"  # nos tâches n'exploitent pas les résultats
    # Celery lit aussi CELERY_RESULT_BACKEND dans l'environnement, prioritaire sur les
    # settings : le .env (Redis Docker) l'y injecte -> on le neutralise pour ce mode.
    os.environ["CELERY_RESULT_BACKEND"] = CELERY_RESULT_BACKEND

if CELERY_TASK_ALWAYS_EAGER:
    # Mode synchrone (tests, ou dev sans worker/Redis) : inutile d'exiger un vrai
    # broker Redis, ça ne fait que retarder chaque requête de ~2 minutes en retries
    # de connexion quand Redis n'est pas démarré.
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    CELERY_TASK_EAGER_PROPAGATES = True

# --- Email ---
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@revue-de-presse.local")

# --- Mistral ---
MISTRAL_API_KEY = env("MISTRAL_API_KEY", default="")
# Modèle d'analyse du texte (résumés, points saillants, rédaction de la revue).
MISTRAL_MODEL = env("MISTRAL_MODEL", default="ministral-8b-latest")
# Modèle de VISION qui lit les photos / PDF scannés (doit déclarer la capacité « vision »).
MISTRAL_VISION_MODEL = env("MISTRAL_VISION_MODEL", default="ministral-8b-latest")
# Rédaction des notices de la revue (une par journal) : modèle plus fidèle que celui des
# résumés intermédiaires (moins de phrases inventées sur les pages courtes).
MISTRAL_REVIEW_MODEL = env("MISTRAL_REVIEW_MODEL", default="ministral-14b-latest")
# Moteur de lecture des photos : auto (Mistral si clé présente, sinon Tesseract) | mistral | tesseract
OCR_ENGINE = env("OCR_ENGINE", default="auto")

# --- Stripe ---
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
STRIPE_PRICE_ID_STARTER = env("STRIPE_PRICE_ID_STARTER", default="")
STRIPE_PRICE_ID_PRO = env("STRIPE_PRICE_ID_PRO", default="")

# --- CamPay (Mobile Money) ---
CAMPAY_APP_USERNAME = env("CAMPAY_APP_USERNAME", default="")
CAMPAY_APP_PASSWORD = env("CAMPAY_APP_PASSWORD", default="")
CAMPAY_WEBHOOK_SECRET = env("CAMPAY_WEBHOOK_SECRET", default="")
CAMPAY_BASE_URL = env("CAMPAY_BASE_URL", default="https://demo.campay.net/api")

# --- Facturation / abonnement ---
# Essai gratuit offert à la création d'une entreprise (0 = désactivé). Sans essai, un
# nouveau compte ne peut lancer aucune revue avant qu'un paiement ait été validé.
TRIAL_DAYS = env.int("TRIAL_DAYS", default=7)
TRIAL_PLAN_CODE = env("TRIAL_PLAN_CODE", default="starter")
SUBSCRIPTION_RENEWAL_REMINDER_DAYS_BEFORE = (3, 1)
# Mode de facturation : « manual » (défaut) = aucun paiement en ligne, le client contacte
# l'équipe (WhatsApp) et un membre du staff active / prolonge l'abonnement dans l'admin
# Django ; « online » = parcours Stripe / Mobile Money / virement en libre-service.
BILLING_MODE = env("BILLING_MODE", default="manual")
# Jours d'accès conservés après la fin de la période payée (le temps de renouveler).
BILLING_GRACE_DAYS = env.int("BILLING_GRACE_DAYS", default=3)
# Contact affiché dans les messages de refus (mode manuel) et sur les factures.
BILLING_CONTACT_WHATSAPP = env("BILLING_CONTACT_WHATSAPP", default="+237 693 42 79 13")
# Factures : numérotation, TVA (19,25 % au Cameroun ; 0 = TVA non applicable) et identité
# légale du vendeur (à faire valider par un comptable avant la première facture).
BILLING_INVOICE_PREFIX = env("BILLING_INVOICE_PREFIX", default="RDP")
BILLING_VAT_RATE = env("BILLING_VAT_RATE", default="19.25")
BILLING_SELLER_NAME = env("BILLING_SELLER_NAME", default="Excelcis Group")
BILLING_SELLER_ADDRESS = env("BILLING_SELLER_ADDRESS", default="")
BILLING_SELLER_RCCM = env("BILLING_SELLER_RCCM", default="")
BILLING_SELLER_NIU = env("BILLING_SELLER_NIU", default="")
BILLING_SELLER_EMAIL = env("BILLING_SELLER_EMAIL", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO"), "propagate": False},
        # WeasyPrint sous-échantillonne les polices via fontTools, qui journalise en INFO
        # plusieurs centaines de lignes par export PDF.
        "fontTools": {"level": "WARNING"},
    },
}
