# API

Documentation interactive générée automatiquement (drf-spectacular) une fois le
backend lancé : `GET /api/docs/` (Swagger UI), schéma brut sur `GET /api/schema/`.

Toutes les routes de domaine (hors `/api/auth/*` et `/api/health/`) exigent un JWT
(`Authorization: Bearer <access>`) et résolvent l'organisation courante via l'en-tête
optionnel `X-Organization-Id` (nécessaire seulement si l'utilisateur appartient à
plusieurs organisations — voir `apps/core/permissions.py`).

## Auth (`apps/accounts/urls.py`)

| Méthode | Route | Description |
|---|---|---|
| POST | `/api/auth/register/` | Crée un utilisateur + sa nouvelle organisation (il en devient owner). |
| POST | `/api/auth/token/` | Login. Renvoie `{access}`, pose le refresh token en cookie httpOnly. |
| POST | `/api/auth/token/refresh/` | Renouvelle l'access token à partir du cookie. |
| POST | `/api/auth/token/logout/` | Blackliste le refresh token et supprime le cookie. |
| GET | `/api/auth/me/` | Utilisateur courant. |
| GET | `/api/auth/invitations/{token}/` | Aperçu public d'une invitation (email, rôle, organisation). |
| POST | `/api/auth/invitations/{token}/accept/` | Accepte une invitation (utilisateur déjà authentifié). |
| POST | `/api/auth/invitations/{token}/register/` | Crée un compte pour un invité qui n'en a pas encore, et le fait rejoindre l'organisation invitée (jamais une nouvelle). |
| GET/PATCH | `/api/organizations/me/` | Organisation courante (PATCH réservé owner/admin). |
| GET | `/api/organizations/me/members/` | Membres de l'organisation. |
| DELETE | `/api/organizations/me/members/{id}/` | Retire un membre (owner/admin ; le dernier owner ne peut pas être retiré). |
| POST | `/api/organizations/me/invite/` | Invite par email (owner/admin). |

## Revues de presse (`apps/press_review/urls.py`)

| Méthode | Route | Description |
|---|---|---|
| GET/POST | `/api/documents/` | Documents en attente (non assignés à un job) / upload d'un fichier (`multipart`, champ `file`). Formats acceptés : PDF, ou photo JPG/PNG/WebP/TIFF/HEIC. La réponse porte `kind` (`pdf`\|`image`), `extraction_status` et, si la lecture a échoué, `extraction_error` (raison lisible). Uploader plusieurs fois pour un job multi-documents. |
| GET/POST | `/api/jobs/` | Liste des jobs / création (`{title, document_ids}` — quota vérifié via l'abonnement). |
| GET | `/api/jobs/{id}/` | Détail + statut + `step_runs` (pour le polling). |
| GET | `/api/jobs/{id}/highlights/?category=<type>` | Points saillants détectés, filtrables par type. |
| GET | `/api/jobs/{id}/review/` | Revue générée (Markdown). |
| GET | `/api/jobs/{id}/review/export/?export_format=pdf\|docx` | URL du fichier exporté (généré à la demande, mis en cache). Le paramètre s'appelle `export_format`, pas `format` — ce dernier est réservé par la négociation de contenu de DRF. |
| POST | `/api/jobs/{id}/retry/` | Relance un job en `FAILED`. |
| GET/POST | `/api/detection-categories/` | Catégories de détection (globales + celles de l'organisation). POST réservé owner/admin. |
| GET/PATCH/DELETE | `/api/detection-categories/{id}/` | Catégories propres à l'organisation uniquement. |

## Facturation (`apps/billing/urls.py`, préfixe `/api/billing/`)

Mode par défaut `BILLING_MODE=manual` : aucun paiement en ligne. Les routes `checkout/*` et
`invoices/{id}/proof/` répondent **403** avec un message renvoyant vers WhatsApp ; l'équipe
active / prolonge les abonnements dans `/admin/billing/subscription/` (voir
`docs/facturation-manuelle.md`).

| Méthode | Route | Description |
|---|---|---|
| GET | `plans/` | Formules actives et leurs limites (public). `price_amount` vaut `null` pour tout non-staff (tarifs « sur devis »). |
| GET | `subscription/` | Abonnement de l'organisation courante : statut, période, `has_access`, `access_until` (fin + délai de grâce), revues du mois, `seats_used` / `seats_limit`. |
| POST | `subscription/cancel/` | Résiliation (owner/admin) : une période payée en cours va jusqu'à son terme (`cancel_at_period_end`) ; essai résilié tout de suite. |
| POST | `subscription/resume/` | Annule une résiliation programmée. |
| GET/PUT/PATCH | `profile/` | Informations de facturation (raison sociale, NIU, RCCM…) ; écriture owner/admin. |
| GET | `invoices/` | Factures de l'organisation (numéro, HT / TVA / TTC). |
| GET | `invoices/{id}/pdf/` | PDF de la facture (membres de l'organisation et staff ; 503 si WeasyPrint indisponible). |
| POST | `invoices/{id}/proof/` | Justificatif de virement, sur une facture `pending` uniquement (mode `online`). |
| POST | `invoices/{id}/review/` | `{approve: bool, reason?}` : valide (formule de la facture + contrôle du montant) ou refuse un virement (réservé `is_staff`). |
| POST | `checkout/stripe/` | `{plan_code}` → URL de Stripe Checkout (mode `online`). |
| POST | `checkout/mobile-money/` | `{plan_code, phone_number}` → demande de collecte CamPay (mode `online`). |
| POST | `checkout/bank-transfer/` | `{plan_code}` → facture à régler par virement (mode `online`). |
| POST | `webhooks/stripe/`, `webhooks/campay/` | Webhooks publics : fermés (403) tant que `STRIPE_WEBHOOK_SECRET` / `CAMPAY_WEBHOOK_SECRET` sont vides, signature vérifiée sinon. |

## Divers

- `GET /api/health/` — supervision (public).
