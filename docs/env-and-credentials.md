# Variables d'environnement & clés externes

Copiez `.env.example` vers `.env` à la racine du repo (lu par `docker-compose.yml` et
par `backend/config/settings/base.py`). Copiez aussi `frontend/.env.example` vers
`frontend/.env` si vous devez surcharger `VITE_API_BASE_URL` (vide par défaut = requêtes
relatives via le proxy Vite, voir `frontend/vite.config.ts`).

Chaque clé externe a un comportement de repli sûr en local : rien ne crash si elle est
vide, le composant concerné passe simplement en mode "mock" explicite.

## Mistral (obligatoire pour un vrai pipeline IA)

| Variable | Où l'obtenir | Effet si vide |
|---|---|---|
| `MISTRAL_API_KEY` | console Mistral AI | `get_mistral_client()` (`apps/ai_pipeline/mistral_client.py`) renvoie `FakeMistralClient` : sorties `[MOCK]` structurellement valides, pipeline démontrable sans clé. |
| `MISTRAL_MODEL` | — | Par défaut `mistral-large-latest`. |

## Stripe (paiement carte)

| Variable | Où l'obtenir | Effet si vide |
|---|---|---|
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | dashboard Stripe (mode test d'abord) | `StripeProvider.enabled = False` : `create_checkout` renvoie un objet `{mock: true}` sans appel réseau. |
| `STRIPE_WEBHOOK_SECRET` | dashboard Stripe → Webhooks | Sans elle, ne configurez pas de webhook Stripe en pointant vers `/api/billing/webhooks/stripe/` (la vérification de signature échouerait). |
| `STRIPE_PRICE_ID_STARTER`, `STRIPE_PRICE_ID_PRO` | Stripe → Produits | À renseigner sur les `Plan.stripe_price_id` correspondants (admin ou migration de données) une fois les produits créés côté Stripe. |

## CamPay (Mobile Money : MTN MoMo + Orange Money)

| Variable | Où l'obtenir | Effet si vide |
|---|---|---|
| `CAMPAY_APP_USERNAME`, `CAMPAY_APP_PASSWORD` | compte CamPay (sandbox puis prod) | `CamPayProvider.enabled = False` : renvoie `{mock: true}`. |
| `CAMPAY_WEBHOOK_SECRET` | dashboard CamPay | Si vide, le webhook `/api/billing/webhooks/campay/` n'exige pas l'en-tête `X-Webhook-Secret` — à définir avant la mise en production. |
| `CAMPAY_BASE_URL` | — | `https://demo.campay.net/api` (sandbox) par défaut ; pointer vers l'environnement de prod CamPay le moment venu. |

## Virement bancaire

Aucune clé externe : `BankTransferProvider` génère juste une facture, l'entreprise
téléverse un justificatif, un membre `is_staff` de l'équipe plateforme valide via
`/api/billing/invoices/{id}/review/` ou l'action admin "Valider le virement"
(`apps/billing/admin.py`).

## Autres

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | À régénérer avant toute mise en production. |
| `DATABASE_URL`, `REDIS_URL`/`CELERY_*` | Postgres et Redis — fournis par `docker-compose.yml` en dev. |
| `EMAIL_HOST`/`EMAIL_PORT` | Pointent vers Mailpit en dev (UI web sur `http://localhost:8025`) ; à remplacer par un vrai SMTP en prod. |
| `FRONTEND_BASE_URL` | Utilisée pour construire les liens dans les emails (invitation, etc.) et les URLs de retour Stripe Checkout. |

## Django admin

`python manage.py createsuperuser` (ou via `docker compose exec backend ...`) donne
accès à `/admin/`, où le client peut :
- affiner les `DetectionCategory` (contenu juridique/critères d'intox réels),
- valider manuellement les virements (`Invoice`),
- ajuster les `Plan` et le planning des tâches Celery beat (`django_celery_beat`).
