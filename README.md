# Revue de Presse

Plateforme SaaS B2B : les entreprises téléversent des PDF (coupures de presse) et un
pipeline IA (Mistral) génère, étape par étape, une revue de presse professionnelle avec
des points saillants catégorisés (risque juridique camerounais, points importants,
intox potentielles). Abonnement mensuel (Stripe, Mobile Money, ou virement bancaire).

- Backend : Django + Django REST Framework + Celery ([backend/](backend))
- Frontend : React + TypeScript + Vite ([frontend/](frontend))
- Docs : [docs/architecture.md](docs/architecture.md) ·
  [docs/pipeline.md](docs/pipeline.md) · [docs/api.md](docs/api.md) ·
  [docs/env-and-credentials.md](docs/env-and-credentials.md)

## Démarrage rapide

```bash
cp .env.example .env
docker compose up -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo_data
docker compose exec backend python manage.py createsuperuser
```

- API : http://localhost:8000/api/ — docs interactives : http://localhost:8000/api/docs/
- Admin Django : http://localhost:8000/admin/
- Emails de dev (Mailpit) : http://localhost:8025

`seed_demo_data` crée un utilisateur de démonstration
(`demo@revue-de-presse.local` / `demo-password-1234`), une organisation avec un
abonnement actif, les catégories de détection par défaut et les plans d'abonnement —
pratique pour tester immédiatement le parcours complet.

Aucune des clés externes (Mistral, Stripe, CamPay) n'est requise pour démarrer : chaque
intégration bascule en mode mock explicite si sa clé est absente (voir
[docs/env-and-credentials.md](docs/env-and-credentials.md)).

### Frontend (hors Docker)

```bash
cd frontend
npm install
npm run dev
```

Ouvre sur http://localhost:5173, proxie `/api/*` vers `http://localhost:8000` en dev
(voir `frontend/vite.config.ts`).

### Tests backend

```bash
docker compose exec backend pytest
```

## Structure du dépôt

```
/backend    Django (apps/core, accounts, press_review, ai_pipeline, billing, notifications)
/frontend   React + TypeScript + Vite
/docs       Documentation technique
```

Voir aussi le [Makefile](Makefile) pour les raccourcis (`make up`, `make migrate`,
`make test`, `make seed`, `make frontend-dev`, ...).
