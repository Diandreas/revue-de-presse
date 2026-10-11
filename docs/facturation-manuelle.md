# Facturation manuelle — procédure de l'équipe

Depuis octobre 2026 (`BILLING_MODE=manual`, valeur par défaut), l'application n'encaisse
rien en ligne et n'affiche aucun prix aux clients (formules « sur devis »). Le client nous
écrit sur WhatsApp (+237 693 42 79 13) depuis la page Abonnement ; un membre de l'équipe
(compte `is_staff`) fait le reste dans l'admin Django.

## Activer ou renouveler un client

1. Convenir du tarif, de la formule et de la durée (1, 3, 6 ou 12 mois) sur WhatsApp, puis
   recevoir le règlement (Mobile Money, virement, espèces, chèque).
2. `/admin/billing/subscription/` → rechercher l'organisation → lien **Enregistrer un
   paiement** (ou bouton du même nom sur la fiche).
3. Choisir la formule payée, la durée, saisir le **montant TTC encaissé**, le mode de
   règlement et la référence (n° de transaction…). Laisser cochée « Prolonger
   l'abonnement ».
4. Valider : une facture **payée** numérotée (RDP-AAAA-NNNN) est créée et l'abonnement est
   prolongé depuis la fin de la période en cours (ou depuis aujourd'hui si elle est
   passée). Le client télécharge la facture PDF depuis sa page Abonnement.

Sans paiement à enregistrer (geste commercial, essai prolongé…) : cocher les abonnements
dans la liste, choisir éventuellement une formule dans la barre d'actions, puis action
**Activer / prolonger 1 mois / 3 mois / 12 mois**.

## Suivi des échéances

- Filtres de la liste : statut, **échéance** (échue, dans 7 jours, dans 30 jours), formule.
- À l'échéance, la tâche « Vérification des abonnements en retard » (7 h 30) passe
  l'abonnement en « En retard » : le client garde l'accès `BILLING_GRACE_DAYS` jours (3 par
  défaut), puis ne peut plus lancer de revue tant qu'il n'est pas prolongé. Un abonnement
  résilié par le client s'arrête à la fin de sa période payée.
- L'essai gratuit (7 jours) s'arrête exactement à sa date de fin.
- Le client voit des bandeaux à J-7 et J-3, puis pendant la grâce.

## Factures

- Numérotation continue par année, jamais réutilisée ; une facture n'est pas supprimable
  (sauf superuser) : l'annuler avec l'action **Refuser**.
- Identité du vendeur : variables `BILLING_SELLER_*` ; TVA : `BILLING_VAT_RATE` (0 = « TVA
  non applicable »). Elles sont **figées sur chaque facture à son émission** : les régler
  avant la première facture.
- Identité du client : « Informations de facturation » saisies par le client (page
  Abonnement) ou par l'équipe (`/admin/billing/billingprofile/`), figées elles aussi.
- PDF : lien **Télécharger** dans `/admin/billing/invoice/`.

## Revenir au paiement en ligne

`BILLING_MODE=online` rouvre les parcours Stripe / Mobile Money / virement (à reconfigurer
avec leurs clés), puis `python manage.py seed_periodic_tasks` pour réactiver la relance
Mobile Money. L'interface client actuelle n'expose plus ces parcours : il faudrait la
compléter.
