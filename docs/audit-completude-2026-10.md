# Audit de complétude — Revue de Presse (11 octobre 2026)

Audit multi-agents en lecture seule : 8 domaines, chaque manque contre-vérifié dans le code par un second agent, puis priorisé. P0 = à régler avant d'encaisser des clients ; P1 = attendu par les clients payants dans les semaines suivantes ; P2 = plus tard. Effort : S (≤ 1 jour), M (quelques jours), L (une semaine ou plus).

## Verdict

Le cœur du produit est abouti et se distingue vraiment. Une photo ou un PDF passe par la lecture IA, puis devient une revue au format camerounais (rubriques, une notice par journal, classement) exportée en PDF et en Word. Le pipeline est robuste, l'isolation entre entreprises est testée et le backend compte environ 186 tests. En revanche, la couche SaaS payante n'est pas prête à encaisser : le webhook CamPay ouvert et la validation des virements permettent d'obtenir un abonnement sans payer, des fichiers déposés peuvent exécuter du script sur le domaine, il n'existe ni sauvegarde hors serveur ni CGU, et le seul moyen de paiement actif (le virement) n'affiche même pas de RIB. La plupart des 9 points P0 sont de petits correctifs (6 sur 9 en effort S) : une fois faits, on peut signer des clients pilotes avec un accompagnement direct (WhatsApp, admin Django). Les P1 couvrent ce qu'une entreprise payante attendra dans les semaines suivantes : e-mail, mot de passe oublié, correction et diffusion de la revue, factures conformes, supervision et CI.

## Déjà solide

- Pipeline IA en arrière-plan robuste. Celery enchaîne 4 étapes avec progression en direct et relance seul sur les erreurs 429/5xx. Un document déjà lu ou une notice déjà rédigée n'est pas recalculé, et une photo illisible n'empêche pas la revue (backend/apps/ai_pipeline/tasks.py, errors.py, mistral_client.py).
- Format de revue de presse camerounais fidèle : rubriques en bandeaux, une notice par journal, fusion des pages d'un même titre, classement du plus lu au moins connu, correction des noms mal lus. C'est couvert par tests/test_press_review_format.py (ai_pipeline/press_format.py, media.py).
- Exports PDF (WeasyPrint protégé contre l'injection HTML et les ressources externes) et Word au même format, mis en cache. Le bouton « Copier le texte » produit une version prête à coller dans WhatsApp (ai_pipeline/export.py, components/PressReviewSheet.tsx).
- Isolation entre organisations revérifiée à chaque requête, avec des identifiants UUID et des tests dédiés (apps/core/permissions.py, tests/test_org_isolation.py).
- Authentification JWT bien conçue. Le jeton d'accès reste en mémoire et le refresh token est dans un cookie httpOnly, Secure et SameSite, limité à /api/auth/. Rotation, liste noire et révocation à la déconnexion sont en place, ainsi qu'une politique de mot de passe de 10 caractères minimum (config/settings/base.py:87-146, api/client.ts).
- Inscription atomique qui crée l'entreprise, le propriétaire et l'essai gratuit de 7 jours. Le quota de revues est appliqué côté serveur, avec des états d'abonnement identiques côté interface et côté serveur (accounts/services.py:32-44, billing/services.py:167-180, features/billing/usage.ts).
- Invitations solides : jeton de 64 caractères, expiration à 7 jours, lien copiable pour WhatsApp. Les actions sensibles sont réservées aux owners et admins (IsOrgAdmin), et le dernier propriétaire ne peut pas être retiré.
- Changement de formule sécurisé : la formule reste en attente (pending_plan_code) jusqu'au paiement. Le parcours par virement est testé de bout en bout et le webhook Stripe vérifie sa signature (tests/test_plan_change.py).
- Interface mobile soignée et entièrement en français : prise de photo directe, compression, HEIC, envois en parallèle, conseils de prise de vue, tiroir mobile, messages d'erreur traduits et bases d'accessibilité.
- Base technique saine : environ 186 tests pytest hermétiques, TypeScript strict, oxlint sans erreur, aucune migration manquante. Les secrets sont dans des variables d'environnement et prod.py impose HTTPS, HSTS et des cookies sécurisés.

## P0 — À régler avant d'encaisser

### Fermer les failles qui permettent d'obtenir un abonnement sans payer (Facturation / sécurité, effort S) ✅ *corrigé le 11/10 pour le webhook CamPay (le volet virement reste à faire)*

**Pourquoi.** Un POST anonyme sur /api/billing/webhooks/campay/ avec une référence vide marque la dernière facture de virement comme payée et renouvelle l'abonnement, formule Enterprise comprise, et peut être rejoué sans fin. Côté virement, la facture ne mémorise pas la formule payée, un justificatif peut être renvoyé sur une facture déjà payée pour la faire revalider, et approve="false" est traité comme une approbation.

**Quoi.** Webhook : répondre 403 si CamPay est désactivé ou si le secret est vide, filtrer sur provider=mobile_money, statut pending et référence non vide, rendre le traitement idempotent, et ajouter des tests HTTP de la vue. Virement : ajouter une clé plan sur Invoice appliquée à la validation avec contrôle du montant, n'accepter un justificatif que sur une facture pending, lire approve avec un BooleanField et ajouter une action « Refuser ». Corriger docs/api.md:55, qui affirme que la signature est vérifiée.

**Preuves.** backend/apps/billing/views.py:194-205 (vérifié : secret contrôlé seulement s'il est défini) et 142-161 ; billing/providers/campay_provider.py:88-104 (vérifié : filtre sur provider_reference seul) ; billing/providers/bank_transfer_provider.py:16-26 ; billing/models.py:71-101 ; billing/services.py:107-140 ; tests/test_billing_webhooks.py (aucun test de la vue).

### Empêcher l'exécution de fichiers piégés déposés par un client (Sécurité, effort M)

**Pourquoi.** Un fichier est accepté si le Content-Type déclaré OU l'extension convient, et il garde son extension d'origine. Le justificatif de virement n'est pas validé du tout, et /media est servi par nginx sur le domaine de l'appli. Un .html ou .svg piégé, ouvert par un autre utilisateur ou par le staff, peut obtenir un jeton via /api/auth/token/refresh/ et prendre le contrôle du compte.

**Quoi.** Vérifier le type réel du fichier (octets magiques, ou ouverture avec Pillow/pdfplumber) et imposer l'extension selon le type détecté. Limiter le justificatif aux PDF, JPG et PNG avec une taille maximale. Dans nginx, servir /media avec Content-Disposition: attachment et X-Content-Type-Options: nosniff, puis contrôler la conf réelle du serveur, qui n'est pas dans le dépôt.

**Preuves.** backend/apps/press_review/serializers.py:41-51 (Content-Type OU extension) ; press_review/models.py:18-25 ; billing/serializers.py:68-69 (FileField sans validation) ; billing/models.py:15-17 ; accounts/views.py:96-127 et config/settings/base.py:143-146 (cookie de refresh sur la même origine).

### Mettre en place des sauvegardes automatiques hors du serveur, avec restauration testée (Exploitation, effort S)

**Pourquoi.** Aucune crontab n'existe pour cette appli. Les seules sauvegardes sont 2 dumps manuels dans /root/backups, sur le même VPS, et backend/mediafiles (documents sources, revues, justificatifs) n'est jamais sauvegardé. Une panne disque, une migration ratée ou une compromission du VPS ferait perdre définitivement les données des clients.

**Quoi.** Ajouter un cron quotidien : pg_dump -Fc plus une archive de mediafiles et du .env, chiffrés et copiés hors du VPS (stockage objet chez un autre fournisseur), avec une rétention de 7 jours, 4 semaines et 12 mois. Documenter la procédure de restauration dans docs/ et la tester chaque mois.

**Preuves.** Faits de prod (aucune crontab, 2 dumps manuels dans /root/backups). Grep pg_dump|backup|sauvegarde|restore dans le dépôt : 0 résultat. config/settings/base.py:99-102 (MEDIA_ROOT sur disque local, pas de stockage distant).

### Publier CGU/CGV, politique de confidentialité et mentions légales, avec acceptation à l'inscription (Légal / conformité, effort M)

**Pourquoi.** Un abonnement de 50 000 à 350 000 FCFA/mois n'a aucun cadre contractuel : renouvellement, résiliation, responsabilité sur les étiquettes « risque juridique » et « intox ». L'envoi des coupures à Mistral, hors du Cameroun, n'est déclaré nulle part alors que la loi n° 2024/017 s'applique. Un service achats ou juridique refusera de signer.

**Quoi.** Rédiger, idéalement avec un juriste, les CGU/CGV, une politique de confidentialité (sous-traitants Mistral, hébergeur et paiement, localisation et durée de conservation), des mentions légales (RCCM, NIU) et un DPA type. Les publier sur des routes publiques avec des liens dans AuthShell, et ajouter une case d'acceptation horodatée et versionnée enregistrée par RegisterSerializer. Vérifier les formalités auprès de l'autorité prévue par la loi.

**Preuves.** frontend/src/App.tsx:24-47 (aucune route légale) ; frontend/src/routes/RegisterPage.tsx:14-19 et backend/apps/accounts/serializers.py:15-26 (aucun champ d'acceptation) ; frontend/src/routes/SettingsPage.tsx:152-170 (seul encart sur la confidentialité) ; grep CGU|CGV|confidentialit|privacy|terms : rien d'autre.

### Permettre de payer par virement sans passer par WhatsApp (Facturation, effort S)

**Pourquoi.** Le virement est le seul moyen de paiement actif en prod, mais la modale n'affiche ni banque, ni titulaire, ni RIB, ni référence à reporter sur le virement. Elle s'ouvre même sur Mobile Money, qui répond « pas encore activé », alors que la page annonce « Mobile Money, carte ou virement ». Le client prêt à payer est bloqué au moment de payer.

**Quoi.** Ajouter des réglages pour la banque, le titulaire et le RIB (ou IBAN/SWIFT), et les afficher dans la modale et sur chaque facture en attente. Ajouter une référence unique (numéro de facture) visible dans la liste des factures. Exposer via l'API un indicateur « activé » par moyen de paiement, ouvrir la modale sur Virement et masquer Mobile Money et carte tant qu'ils ne sont pas configurés.

**Preuves.** backend/apps/billing/providers/bank_transfer_provider.py:16-33 ; frontend/src/routes/BillingPage.tsx:253 (Mobile Money par défaut), 411-431, 497-503, 588 et 640-651 ; .env de prod : variables CAMPAY_* et STRIPE_* vides.

### Fiabiliser l'expiration et le renouvellement des abonnements (Facturation, effort M)

**Pourquoi.** grants_access accorde l'accès à tout abonnement ACTIVE sans regarder current_period_end. Si seed_periodic_tasks, une commande non documentée, n'a pas été lancée en prod, un abonnement payé une seule fois n'expire jamais. Si elle l'a été, un client qui paie par virement est coupé dès J+1 (le statut past_due bloque les revues), sans facture de renouvellement, sans pouvoir payer d'avance, et les rappels par e-mail ne partent pas.

**Quoi.** Vérifier tout de suite /admin/django_celery_beat/ en prod, puis créer les tâches périodiques par une migration de données. grants_access doit vérifier current_period_end, délai de grâce compris. Générer la facture de renouvellement à J-7, permettre « Renouveler » sur la formule active, garder l'accès pendant la grâce si un justificatif attend validation, prolonger depuis max(now, current_period_end), afficher un bandeau dans l'appli à J-7 et J-3, et tester ces tâches.

**Preuves.** backend/apps/billing/services.py:75-81 (vérifié : ACTIVE donne accès sans contrôle de date), 133-140 et 167-180 ; billing/tasks.py:16-102 ; billing/management/commands/seed_periodic_tasks.py (cité nulle part) ; frontend/src/routes/BillingPage.tsx:165-169 et 224 ; frontend/src/components/UsageCard.tsx:66-93.

### Passer Mistral sur une offre payante avant le premier client (Qualité IA / exploitation, effort S)

**Pourquoi.** Une seule clé gratuite sert tous les clients : une revue de 50 photos peut saturer la limite de débit et faire échouer les revues des autres après 3 relances. Les modèles disponibles changent sans préavis. Les conditions d'usage des données de l'offre gratuite, notamment la réutilisation pour l'entraînement, n'ont pas été vérifiées alors qu'il s'agit de documents clients.

**Quoi.** Souscrire une offre payante avec un plafond de dépenses et une alerte de budget. Vérifier les conditions de traitement des données et les reprendre dans la politique de confidentialité, puis revoir le choix des modèles selon ce qui devient disponible.

**Preuves.** config/settings/base.py:209-216 (une clé et des modèles uniques) ; backend/apps/ai_pipeline/mistral_client.py:68-79 ; ai_pipeline/tasks.py:52-53 ; contexte fourni : compte gratuit, seuls les modèles ministral-* fonctionnent.

### Limiter le débit des requêtes et fermer l'administration au public (Sécurité, effort S)

**Pourquoi.** La connexion, l'inscription, les invitations publiques et les dépôts n'ont aucune limite de débit. On peut deviner des mots de passe, saturer le CPU ou créer des essais à la chaîne qui vident le quota Mistral et le disque. /admin/, qui donne accès à toutes les organisations et à la validation des paiements, et /api/docs et /api/schema sont publics, sans 2FA ni filtrage IP.

**Quoi.** Configurer CACHES sur Redis, puis activer DEFAULT_THROTTLE_CLASSES et des ScopedRateThrottle stricts sur auth/token, auth/register, les invitations et l'upload. Ajouter limit_req dans nginx sur /api/auth/ et /admin/login/. Restreindre /admin/ par IP, ajouter django-otp pour le staff et passer SERVE_PERMISSIONS de spectacular à IsAdminUser.

**Preuves.** config/settings/base.py:107-127 (ni THROTTLE, ni CACHES, ni SERVE_PERMISSIONS) ; config/urls.py:18 et 23-24 ; backend/apps/accounts/views.py:47-93 (AllowAny) ; backend/requirements/base.txt (ni django-axes ni django-otp).

### Rendre la connexion insensible à la casse de l'e-mail (Comptes, effort S)

**Pourquoi.** L'e-mail est enregistré en minuscules à l'inscription, mais la connexion fait une recherche exacte. Quelqu'un inscrit avec « Jean.Ndjock@… » qui retape exactement la même adresse est refusé. Sans « mot de passe oublié », il se croit bloqué.

**Quoi.** Surcharger UserManager.get_by_natural_key avec email__iexact, ou mettre l'e-mail en minuscules avant TokenObtainPairSerializer. Faire aussi un lower() dans LoginPage et ajouter un test dans tests/test_auth_flow.py.

**Preuves.** backend/apps/accounts/serializers.py:22 et services.py:49 (lower() à l'inscription, vérifié) ; accounts/views.py:78 (TokenObtainPairSerializer standard) ; accounts/models.py:15-39 (aucun get_by_natural_key, vérifié par grep) ; frontend/src/routes/LoginPage.tsx:14-17.


## P1 — Attendu par les clients payants

### Activer l'e-mail transactionnel et les notifications (Comptes / notifications, effort M)

**Pourquoi.** Les settings ne lisent ni EMAIL_HOST_USER ni EMAIL_HOST_PASSWORD, et la prod n'a pas d'identifiants SMTP : invitations et rappels de renouvellement échouent sans que personne le sache (fail_silently). Rien ne prévient l'utilisateur quand sa revue est prête ou a échoué, ni le staff quand un justificatif de virement arrive.

**Quoi.** Lire EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_SSL et EMAIL_TIMEOUT, brancher un fournisseur transactionnel (Brevo, Mailjet ou SES) avec SPF, DKIM et DMARC, et envoyer via une tâche Celery avec réessais. Ensuite : e-mail « revue prête » ou « échec », alertes au staff (justificatif déposé, inscription, job échoué), rappels de fin d'essai à J-2 et J0, et indicateur dans l'appli.

**Preuves.** config/settings/base.py:201-206 ; backend/apps/accounts/services.py:15-29 et 59 ; billing/tasks.py:68-102 ; billing/views.py:139-151 ; apps/notifications/models.py (vide) ; ai_pipeline/tasks.py:428-429.

### Compte en libre-service : mot de passe oublié, changement de mot de passe, profil (Comptes, effort M)

**Pourquoi.** Un utilisateur qui oublie son mot de passe dépend d'un superuser qui lui transmet un mot de passe en clair, qu'il ne peut ensuite pas changer. Il ne peut pas non plus corriger son nom ni déconnecter ses autres appareils.

**Quoi.** Ajouter POST /auth/password/reset/ et /confirm/ (PasswordResetTokenGenerator, débit limité) avec les pages front correspondantes. En attendant le SMTP, permettre au staff ou à l'owner de générer un lien de réinitialisation à partager, comme pour les invitations. Ajouter PATCH /auth/me/ et POST /auth/password/change/, avec révocation des autres sessions via CHECK_REVOKE_TOKEN de SIMPLE_JWT.

**Preuves.** backend/apps/accounts/urls.py:20-43 (aucune route de réinitialisation) ; accounts/views.py:146-150 (MeView en GET seulement) ; accounts/serializers.py:8-12 (lecture seule) ; frontend/src/routes/SettingsPage.tsx:174-191 ; config/settings/base.py:132-141.

### Faire respecter la hiérarchie des rôles et gérer les comptes membres de plusieurs organisations (Comptes / équipe, effort M)

**Pourquoi.** Un admin peut inviter un « owner » via l'API puis évincer le propriétaire client, sans laisser de trace. Un utilisateur qui accepte une deuxième organisation (essai perso puis invitation de son employeur) est bloqué par un message technique 403 sur « X-Organization-Id ». Un membre retiré tombe sur une appli à moitié ouverte.

**Quoi.** Réserver au seul owner l'invitation, la promotion et le retrait des owners et des admins, avec des tests. Ajouter le changement de rôle (PATCH), le transfert de propriété et « Quitter l'organisation ». À court terme, refuser avec un message clair l'acceptation par un compte déjà membre ailleurs. Ensuite, GET /auth/me/organizations/, un sélecteur d'organisation, l'en-tête envoyé par client.ts et un écran dédié quand l'utilisateur n'a plus d'organisation.

**Preuves.** backend/apps/accounts/serializers.py:59-61 ; accounts/services.py:75-79 et 109-118 ; accounts/views.py:187-212 ; apps/core/permissions.py:38-46 ; frontend/src/auth/AuthContext.tsx:11-33 ; frontend/src/routes/TeamPage.tsx:36 et 314.

### Faire respecter les limites des formules et protéger l'essai gratuit (Abonnement, effort M)

**Pourquoi.** max_seats n'est jamais appliqué : un client Starter (3 places) peut inviter 50 collègues, ce qui supprime l'intérêt de Pro et d'Enterprise. Une nouvelle adresse e-mail suffit pour obtenir un nouvel essai qui consomme le quota Mistral partagé. Les dépôts de fichiers ne vérifient pas l'abonnement, et aucun numéro de contact ne permet de relancer les essais.

**Quoi.** Comparer membres et invitations en attente à plan.max_seats à l'invitation et à l'acceptation, avec un lien vers la page Abonnement. Refuser le dépôt et la relance si grants_access est faux, et ne pas décompter une revue en échec abandonnée. Demander un numéro WhatsApp à l'inscription, vérifier l'e-mail avant l'essai une fois le SMTP en place, et lister les essais en cours dans l'admin.

**Preuves.** backend/apps/accounts/services.py:47-106 (aucun contrôle de max_seats) ; billing/services.py:157-164 ; press_review/views.py:107-121 et 274-292 ; accounts/models.py:42-66 (ni téléphone ni vérification) ; frontend/src/routes/TeamPage.tsx:241-287.

### Émettre des factures conformes (proforma et facture acquittée) (Facturation, effort M)

**Pourquoi.** Les factures n'ont ni numéro, ni identité fiscale (raison sociale, NIU, RCCM), ni montants HT/TVA/TTC, ni PDF. Une entreprise camerounaise ne peut ni régler ni comptabiliser sans facture. De plus, les factures sont supprimées en cascade avec l'organisation, et chaque clic crée une nouvelle facture en attente.

**Quoi.** Après l'avis d'un comptable sur le régime de TVA (19,25 %), ajouter une numérotation séquentielle, les informations de facturation du client et du vendeur, les montants HT/TVA/TTC et la mention HT ou TTC sur les prix. Générer en PDF (WeasyPrint) une proforma puis une facture acquittée, téléchargeables. Passer les relations d'Invoice en PROTECT et réutiliser la facture déjà en attente.

**Preuves.** backend/apps/billing/models.py:71-101 ; accounts/models.py:62-72 ; billing/urls.py:17-29 (aucun endpoint PDF) ; billing/providers/bank_transfer_provider.py:16-33 ; frontend/src/routes/BillingPage.tsx:480-527.

### Relire, corriger et diffuser la revue depuis l'appli (Fonctionnalités cœur, effort L)

**Pourquoi.** La revue, les points clés et le titre sont en lecture seule : une erreur de l'IA (journal mal nommé, « JOURNAL NON IDENTIFIÉ », faux positif) part telle quelle dans le PDF, à moins de retoucher le Word hors de l'appli. La diffusion, cœur de l'usage au Cameroun (WhatsApp, e-mail à la direction), se fait entièrement à la main.

**Quoi.** Ajouter PATCH /jobs/{id}/review/ (notices, titre, date, ordre) et PATCH sur les points clés (masquer, changer de catégorie), vider le cache des exports et garder la version IA d'origine, puis rendre PressReviewSheet modifiable. Ajouter le partage natif du PDF sur mobile (navigator.share, donc WhatsApp), puis une liste de diffusion par e-mail, journalisée, qui fait passer la revue à l'état EXPORTED.

**Preuves.** backend/apps/press_review/views.py:227-271 (GET seulement) ; press_review/serializers.py:106-123 (lecture seule) ; press_review/urls.py:17-29 ; ai_pipeline/tasks.py:394-406 ; frontend/src/routes/JobDetailPage.tsx:288-349 ; frontend/src/components/PressReviewSheet.tsx:46-54.

### Donner au client la maîtrise de ses données : fichiers privés, suppression, export (Données / sécurité, effort L)

**Pourquoi.** Les fichiers sont servis par nginx sans authentification, via des liens valables à vie (lien transféré, ancien membre), alors que Paramètres promet qu'ils ne sont « visibles que par les membres ». Un client ne peut supprimer ni une revue, ni son compte, ni son organisation, ni exporter ses données. Même une suppression via /admin laisse les fichiers sur le disque.

**Quoi.** Servir les fichiers via une vue Django qui vérifie l'appartenance puis renvoie un X-Accel-Redirect vers un emplacement nginx « internal » (ou des URL signées à courte durée). Ajouter la suppression et le renommage d'une revue, « Fermer l'organisation » (owner, avec délai de grâce), la suppression du compte et un export ZIP. Supprimer les fichiers en post_delete, purger les documents non rattachés et documenter une durée de conservation.

**Preuves.** backend/apps/press_review/views.py:124-135, 219-224 et 270-271 (URL brute du fichier) ; press_review/models.py:18-30 ; billing/models.py:15-17 ; accounts/urls.py:20-43 (aucune suppression de compte ni d'organisation) ; frontend/src/routes/SettingsPage.tsx:159 ; grep post_delete|X-Accel : 0 résultat.

### Fiabiliser les points clés et les notices livrés (Qualité IA, effort M)

**Pourquoi.** Les extraits cités entre guillemets ne sont jamais vérifiés dans le texte OCR et aucun seuil de confiance ne filtre l'annexe. La détection tourne sur ministral-8b, le modèle que le projet juge lui-même le moins fidèle, le nom du journal n'est pas contrôlé, et l'annexe cite le nom du fichier (« WhatsApp Image….jpeg ») au lieu du journal. Une citation inventée dans le PDF remis à la direction détruit la confiance dès la première revue.

**Quoi.** Vérifier chaque extrait par une recherche approchée dans le texte (sinon l'écarter ou le marquer « non vérifié »), appliquer un seuil réglable à l'export et passer la détection sur ministral-14b à température 0. Contrôler aussi le nom du journal et retirer « presse » des mots-clés par défaut. Attribuer chaque point clé à son journal, signaler dans le livrable les pages non lues et les notices de repli, et constituer un jeu d'évaluation de 30 à 50 vraies pages.

**Preuves.** backend/apps/ai_pipeline/tasks.py:246, 301-329 et 383-401 ; ai_pipeline/prompts/highlight_detection.py:25-30 ; ai_pipeline/export.py:115-140 et 213-235 ; press_review/management/commands/seed_default_categories.py:21 ; config/settings/base.py:211-216 ; docs/pipeline.md:105 (fidélité mesurée sur une seule photo).

### Maîtriser la charge, le coût de l'IA et les gros PDF (Qualité IA / exploitation, effort M)

**Pourquoi.** Il n'y a aucune limite de débit, ni globale ni par organisation, et aucune mesure des jetons consommés par revue ou par client. Une relance recalcule tous les résumés et points clés. Un PDF de centaines de pages est converti d'un coup en mémoire sur le VPS partagé, et un PDF « Les unes du jour » ne donne qu'une seule notice, attribuée à un seul journal.

**Quoi.** Ajouter un limiteur Redis global et par organisation, et plafonner pages et documents selon la formule. Convertir les PDF page par page avec un cache par page, et proposer l'option « une page = un journal ». Mettre en cache résumés et points clés par extrait, journaliser chaque appel IA (organisation, revue, étape, modèle, jetons, latence) et refuser de démarrer en prod sans MISTRAL_API_KEY.

**Preuves.** backend/apps/ai_pipeline/ocr.py:97-102 (toutes les pages en mémoire) ; ai_pipeline/tasks.py:202-251 et 370-401 ; ai_pipeline/mistral_client.py:91-112 et 183-187 ; config/celery.py (aucun rate_limit) ; billing/services.py:157-180 ; press_review/serializers.py:7 et 103.

### Superviser la prod et éviter les pages blanches (Exploitation, effort M)

**Pourquoi.** Il n'y a ni Sentry ni alerte : une erreur 500, un worker arrêté ou une revue bloquée « en cours » ne sont découverts que par le client, et une revue bloquée ne peut pas être relancée (la relance exige l'état FAILED). Côté front, il n'y a pas d'ErrorBoundary alors que toutes les pages sont chargées à la demande : après chaque déploiement, un onglet resté ouvert affiche une page blanche.

**Quoi.** Brancher Sentry (Django, Celery et React) et un moniteur d'uptime externe sur /api/health/, étendu à Redis et au worker. Ajouter une tâche planifiée qui passe en FAILED les revues sans progression, activer task_reject_on_worker_lost et la rotation des logs PM2 (pm2-logrotate). Ajouter une ErrorBoundary racine avec un bouton « Recharger » et un rechargement automatique unique sur vite:preloadError.

**Preuves.** config/settings/base.py:153-175 et 242-253 (logs en console seulement) ; backend/apps/core/views.py:13-16 (SELECT 1 seulement) ; press_review/views.py:277-280 ; frontend/src/App.tsx:9-18 (pages en lazy()) ; frontend/src/main.tsx:14-26 ; contexte fourni : aucune variable SENTRY en prod.

### Industrialiser : CI, déploiement versionné, dépendances à jour (Qualité logicielle / déploiement, effort L)

**Pourquoi.** Sans CI, les tests, tsc et oxlint ne tournent qu'à la main : l'export PDF a déjà cassé en prod à cause de pydyf, et aucun test ne génère un vrai PDF. La prod tourne sur une branche feat/ sans tag, déployée par tar+scp. Les points d'entrée prennent config.settings.dev par défaut, SECRET_KEY retombe sur une valeur publique, et Django 5.0 ne reçoit plus de correctifs de sécurité depuis avril 2025.

**Quoi.** Mettre en place GitHub Actions : pytest avec Postgres et Redis, un test qui vérifie que le PDF généré commence par %PDF, des tests HTTP des webhooks et des tâches planifiées, tsc, oxlint, build et check --deploy. Écrire un script de déploiement depuis un tag et docs/deploiement.md (PM2, nginx, migrate, seed_periodic_tasks, retour arrière). Faire exiger DJANGO_SECRET_KEY par prod.py, migrer vers Django 5.2 LTS, verrouiller les dépendances avec leurs hashes, ajouter pip-audit et Dependabot, et compléter .env.example.

**Preuves.** Aucun dossier .github, aucun tag git ; backend/requirements/base.txt:1-3 et 18-23 ; config/wsgi.py:5, config/celery.py:5, manage.py:7 ; config/settings/base.py:16 ; config/settings/prod.py:1-10 ; tests/test_export_rendering.py (HTML uniquement).

### Créer une vitrine publique avec les tarifs (Expérience / commercial, effort M)

**Pourquoi.** La racine du site renvoie vers /login : sur mobile, un prospect ne voit qu'un formulaire, sans savoir ce que fait le produit, sans exemple de revue ni prix en FCFA (la liste des formules exige d'être connecté). Les liens partagés sur WhatsApp ou LinkedIn s'affichent sans image.

**Quoi.** Créer une page d'accueil publique sur « / » : proposition de valeur, exemple de revue, les 3 formules en FCFA (HT ou TTC précisé), essai de 7 jours, FAQ et appels à l'action (démo WhatsApp, inscription), avec le tableau de bord déplacé sous /dashboard. Ouvrir GET /api/billing/plans/ sans authentification, et ajouter les balises og: et twitter: avec une image, un robots.txt et une page Aide.

**Preuves.** frontend/src/App.tsx:28-35 ; frontend/src/auth/RequireAuth.tsx:17-18 ; frontend/src/components/AuthShell.tsx:75 et 111-137 (présentation masquée sur mobile) ; backend/apps/billing/views.py:31-34 (IsAuthenticated) ; frontend/index.html ; frontend/public (favicon.svg seul).


## P2 — Plus tard

### Productivité éditoriale : régénérer une notice, compléter une revue, éviter les doublons, revue programmée (Fonctionnalités cœur, effort M)

**Pourquoi.** Une notice ratée ou une page oubliée oblige à refaire toute la revue, avec de nouveaux appels IA et une revue de plus décomptée du quota. Une une envoyée deux fois répète les mêmes phrases. Enfin, la revue dépend entièrement d'une action manuelle chaque matin.

**Quoi.** Ajouter une régénération ciblée d'une notice et l'ajout de pages à une revue prête, sans décompter le quota. Calculer une empreinte SHA-256 au dépôt et dédoublonner résumés et points clés. Permettre une heure de bouclage par organisation, avec un rappel et un envoi automatique dès que la revue est prête.

**Preuves.** backend/apps/press_review/views.py:277-280 ; press_review/services/jobs.py:23-31 ; press_review/services/pipeline.py:28 ; press_review/models.py:72-107 ; ai_pipeline/press_format.py:131-133 ; billing/management/commands/seed_periodic_tasks.py:4-20.

### Archives, personnalisation des exports et langue (Fonctionnalités cœur, effort L)

**Pourquoi.** L'historique s'arrête aux 100 dernières revues, sans recherche : la limite sera atteinte après environ 5 mois d'usage quotidien. Les exports ne portent pas le logo du client, la liste des journaux et des rubriques est codée en dur, et le réglage « Langue des revues » s'affiche sans aucun effet.

**Quoi.** Mettre en place une vraie pagination, une recherche plein texte PostgreSQL (titre, notices, points clés) et des filtres par date. Permettre un logo et une couleur de bandeau par organisation, avec invalidation du cache des exports. Créer un modèle Media modifiable par organisation, initialisé depuis media.py, et produire la revue en anglais via default_locale, ou masquer ce réglage en attendant.

**Preuves.** frontend/src/routes/DashboardPage.tsx:258-273 ; backend/apps/core/pagination.py:4-7 ; ai_pipeline/export.py:85-94 et 173-182 ; ai_pipeline/media.py:21-64 ; accounts/models.py:62-73 ; frontend/src/routes/SettingsPage.tsx:141.

### Facturation avancée et suivi des encaissements (Facturation, effort L)

**Pourquoi.** La résiliation coupe l'accès immédiatement malgré la période payée, ce qui créera des litiges une fois Stripe ou Mobile Money actifs. Seul le mensuel existe, alors que les grandes structures paient à l'année sur proforma, et le staff n'a ni vue du revenu mensuel ni alertes. CamPay et Stripe restent à finaliser : URL de bac à sable par défaut, et Stripe créerait un second abonnement à chaque changement de formule.

**Quoi.** Faire résilier en fin de période (cancel_at_period_end, avec possibilité d'annuler la résiliation) et aligner les CGV. Ajouter un intervalle annuel avec remise et le prorata, et une vue staff : justificatifs en attente, essais à J-2, retards, revenu mensuel, prolongation d'essai, paiement hors ligne. Activer CamPay en prod (URL, secret, vérification du statut) et corriger Stripe, ou le retirer s'il n'est pas ouvert aux entreprises camerounaises.

**Preuves.** backend/apps/billing/services.py:151-154 ; billing/models.py:21-22 et 64 ; billing/admin.py:9-44 ; config/settings/base.py:231 (bac à sable CamPay par défaut) ; billing/views.py:69-85 ; billing/providers/stripe_provider.py:34-58.

### Confort technique et défense en profondeur (Qualité logicielle / sécurité, effort L)

**Pourquoi.** Plusieurs manques ne bloquent pas la vente mais s'additionnent. Il n'y a pas de journal d'audit (qui a retiré un owner ou validé un paiement ?), pas de 2FA pour les owners, pas de CSP, et HSTS ne dure que 7 jours. On n'a non plus ni tests frontend, ni préproduction, ni schéma OpenAPI exploitable, ni lint Python, ni garde-fou contre l'injection de consignes dans les prompts, et l'appli ne s'installe pas sur l'écran d'accueil du téléphone.

**Quoi.** Ajouter un modèle AuditEvent par organisation, consultable par l'owner, une 2FA optionnelle pour les owners et admins, une CSP stricte et HSTS à 1 an dans nginx, et délimiter le texte source dans les prompts. Mettre en place Vitest et 2 ou 3 scénarios Playwright, une préproduction avant d'activer CamPay et Stripe, @extend_schema et ruff. Côté interface : manifest PWA, meilleurs contrastes, renouvellement des invitations expirées, tolérance à la rotation du refresh token, et retrait de backend/test_mediafiles de git.

**Preuves.** Grep audit|LogEntry dans apps : 0 résultat ; config/settings/prod.py:8 ; ai_pipeline/prompts/chunk_summary.py:9 et highlight_detection.py:30 ; frontend/package.json (aucun script de test) ; backend/apps/accounts/services.py:53-58 ; config/settings/base.py:135-136 ; config/settings/test.py:38.

## Limites de cet audit (non examiné)

- Droit d'auteur et droits des éditeurs de presse : il n'a pas été vérifié s'il est légal de résumer puis de redistribuer le contenu des journaux camerounais, ni si un accord avec les éditeurs ou une société de gestion collective serait nécessaire.
- Statut juridique et fiscal du vendeur (régime de TVA, immatriculation, obligations de facturation) : le point est seulement signalé, rien n'a été validé avec un comptable.
- Stratégie tarifaire et marge : prix de 50 000 à 350 000 FCFA face à la concurrence et aux revues faites à la main, coût IA réel par revue une fois Mistral payant, rentabilité de chaque formule.
- Validation du marché et cycle de vente : besoins réels et disposition à payer des entreprises camerounaises, marchés publics (appels d'offres, bons de commande), processus commercial et CRM.
- Support et accompagnement des clients : SLA, horaires, organisation du canal WhatsApp, formation, documentation utilisateur, onboarding des pilotes.
- Configuration réelle du serveur, absente du dépôt et non auditée faute d'accès à la prod : nginx (en-têtes, /media, limites), pare-feu, SSH, mises à jour de l'OS, cloisonnement avec les autres applis du VPS, renouvellement automatique du certificat TLS, pm2-logrotate, valeur réelle de DJANGO_SETTINGS_MODULE.
- Performance et charge réelles : durée d'une revue de 20 à 50 photos en prod, capacité du VPS, comportement sur réseau mobile 3G au Cameroun, poids du bundle frontend. Rien n'a été mesuré.
- Qualité réelle de l'OCR, des notices et des points clés sur un échantillon de vrais journaux camerounais : aucune mesure dans cet audit.
- Délivrabilité des e-mails (SPF, DKIM, DMARC du domaine mirlab.cloud) et exigences des prestataires de paiement (KYC marchand CamPay, ouverture de Stripe aux entreprises camerounaises).
- Mesure de l'usage du produit (conversion essai → payant, usage par client) et compatibilité avec les navigateurs et appareils réels (vieux Android, Safari iOS), y compris l'accessibilité testée avec de vrais outils.
- Sécurité du poste de développement d'où l'on déploie par tar+scp, et qui détient probablement les secrets de prod.
- Le bouton démo WhatsApp, exclu volontairement car il est en cours d'ajout.
