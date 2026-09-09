# Architecture

## Vue d'ensemble

SaaS B2B multi-tenant : les entreprises téléversent des PDF (coupures de presse), un
pipeline IA (Mistral) génère une revue de presse structurée avec des points saillants
catégorisés (risque juridique, point important, intox potentielle). Facturation par
abonnement mensuel (Stripe, Mobile Money via CamPay, ou virement bancaire).

```
/backend    Django + DRF + Celery
/frontend   React + TypeScript + Vite
```

## Multi-tenant

Row-level : chaque ressource de domaine porte une FK `organization`, et tous les
querysets sont filtrés côté serveur par `request.organization` — jamais par un
identifiant fourni par le client. Voir `apps/core/permissions.py:OrganizationContextMixin`,
qui résout l'organisation courante à partir de l'en-tête `X-Organization-Id` (ou de
l'unique organisation de l'utilisateur si non ambigu) et vérifie l'appartenance.

## Apps Django

| App | Rôle |
|---|---|
| `apps.core` | Base commune : `TimeStampedModel` (UUID + horodatage), permissions org, pagination, gestion d'erreurs, `/api/health/`. |
| `apps.accounts` | `User` (email), `Organization`, `Membership` (owner/admin/member), `Invitation`. Auth JWT avec refresh en cookie httpOnly. |
| `apps.press_review` | Domaine central : `DetectionCategory`, `SourceDocument`, `PressReviewJob`, `PipelineStepRun`, `Highlight`, `GeneratedReview`. Endpoints upload/jobs/catégories. |
| `apps.ai_pipeline` | Mécanique IA : client Mistral, extraction PDF/OCR, découpage, prompts, tâches Celery, export PDF/DOCX. Ne définit aucun modèle propre — écrit dans les modèles de `press_review`. |
| `apps.billing` | `Plan`, `Subscription`, `Invoice`, 3 providers de paiement derrière une interface commune, tâches Celery beat de relance. |
| `apps.notifications` | Réservée aux futures notifications transverses (actuellement, les emails d'invitation/facturation sont envoyés directement par `accounts`/`billing`). |

Convention par app : `models.py`, `serializers.py`, `views.py` (viewsets DRF fins),
`urls.py`, `admin.py`, `permissions.py`, `services.py`/`services/` — la logique métier
vit dans les services, jamais dans les vues ou les serializers.

## Authentification

`POST /api/auth/token/` renvoie l'access token (courte durée, 30 min) dans le corps de
la réponse et pose le refresh token (14 jours) en cookie **httpOnly**. Le frontend garde
l'access token en mémoire (jamais en `localStorage`) pour réduire l'exposition XSS ; au
chargement de l'app, un appel silencieux à `/api/auth/token/refresh/` restaure la
session via le cookie. Voir `backend/apps/accounts/views.py` et
`frontend/src/api/client.ts` (intercepteur de refresh à vol unique).

## Frontend

React 19 + TypeScript + Vite + Tailwind CSS v4. TanStack Query gère le cache serveur et
le polling (`refetchInterval` sur le statut d'un job). En dev, le proxy Vite
(`vite.config.ts`) fait passer `/api/*` vers `http://localhost:8000`, ce qui évite tout
problème de CORS/cookies en local (front et back apparaissent same-origin).

Voir aussi [pipeline.md](pipeline.md), [api.md](api.md) et
[env-and-credentials.md](env-and-credentials.md).
