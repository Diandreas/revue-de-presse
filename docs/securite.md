# Sécurité : fichiers déposés, fichiers privés, limitation de débit, administration

Ce document décrit les protections ajoutées en octobre 2026 (audit `docs/audit-completude-2026-10.md`,
points P0 « fichiers piégés », P0 « limitation de débit et administration » et P1 « fichiers privés »)
et la configuration serveur qu'elles demandent.

## 1. Fichiers déposés : type réel, extension imposée

Code : `backend/apps/core/uploads.py` (champ DRF `VerifiedFileField`).

- Le nom et le Content-Type envoyés par le navigateur ne sont jamais crus. Le type est lu dans les
  premiers octets (signature PDF, JPEG, PNG, WebP, HEIC/HEIF), puis confirmé en ouvrant le fichier :
  PDFium (`pypdfium2`) pour les PDF, Pillow (+ `pillow-heif`) pour les images.
- Le fichier est renommé avec l'extension du type **détecté** avant stockage. Les fonctions
  `upload_to` des modèles reprennent cette extension. Le nom choisi par l'utilisateur reste affiché
  (`SourceDocument.original_filename`).
- Documents sources : PDF, JPG, PNG, WebP, HEIC/HEIF, 30 Mo au plus. SVG, HTML, GIF, BMP et TIFF
  sont refusés, ainsi que les polyglottes (signature valide suivie d'autre chose) et les PDF
  tronqués ou protégés par mot de passe.
- Justificatif de virement : PDF, JPG ou PNG, 10 Mo au plus.

Pour un nouveau champ de dépôt, utiliser `VerifiedFileField(allowed_types=..., max_size=...,
formats_message=...)` plutôt que `serializers.FileField()`.

## 2. Fichiers privés : liens signés à courte durée de vie

Code : `backend/apps/core/media.py`.

- Le stockage par défaut (`STORAGES["default"]` = `PrivateMediaStorage`) ne renvoie plus d'URL
  publique `/media/…`. `FieldFile.url` produit un lien signé :
  `/api/media/<échéance>/<signature>/<chemin>`. La signature HMAC, calculée avec `SECRET_KEY`, lie le
  lien au chemin exact et à l'échéance. Tous les champs de fichier de l'API en profitent sans code
  supplémentaire : documents, aperçus, exports PDF/Word, justificatifs, et liens de l'admin Django.
- Durée de vie : `MEDIA_URL_MAX_AGE`, 30 min par défaut. L'échéance est arrondie par fenêtre de
  10 min, si bien que l'URL d'un aperçu ne change pas d'un rafraîchissement à l'autre et que le
  navigateur la garde en cache. Un lien vit donc entre 20 et 30 min. Un lien expiré répond 403
  « Lien expiré ou invalide » : il suffit de recharger la page de l'application.
- Pourquoi une signature plutôt que le jeton de l'utilisateur ? Le jeton d'accès vit en mémoire
  dans l'application React, et une balise `<img>` ne peut pas l'envoyer. Seuls des endpoints
  réservés aux membres de l'organisation délivrent ces liens.
- En-têtes de chaque fichier servi : `X-Content-Type-Options: nosniff`,
  `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox` (document isolé,
  aucun script), `Content-Disposition` (`inline` pour les images, `attachment` pour PDF, Word et le
  reste), `Referrer-Policy: no-referrer` et `Cache-Control: private`.
- Production (`MEDIA_X_ACCEL_REDIRECT=True`) : Django vérifie la signature puis répond
  `X-Accel-Redirect: /protected-media/<chemin>`. nginx envoie le fichier depuis un emplacement
  `internal` (`ops/nginx/presse-media.conf`), sans bloquer de worker gunicorn.
- Développement (`MEDIA_X_ACCEL_REDIRECT=False`) : Django envoie lui-même le fichier. `/media/` n'est
  plus servi, même en `DEBUG`.

## 3. Limitation de débit

Code : `backend/apps/core/throttling.py` ; taux dans `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`
(`config/settings/base.py`).

| Portée | Taux | Clé | S'applique à |
|---|---|---|---|
| `anon` | 120/min | IP | toute requête anonyme (hors `/api/health/`) |
| `user` | 600/min | utilisateur | toute requête authentifiée (le suivi d'une revue interroge l'API toutes les 2,5 s) |
| `login` | 10/min | IP | `POST /api/auth/token/` |
| `login_email` | 10/min | e-mail saisi | `POST /api/auth/token/` |
| `register` | 5/heure | IP | `POST /api/auth/register/` |
| `invitations` | 60/heure | IP ou utilisateur | aperçu, acceptation et inscription par invitation, `POST /api/organizations/me/invite/` |
| `password_reset` | 10/heure | IP ou utilisateur | toute vue qui déclare `throttle_scope = "password_reset"` |
| `password_reset_email` | 5/heure | e-mail saisi | ces mêmes vues (champ `email` du corps) |
| `uploads` | 120/heure | utilisateur | `POST /api/documents/`, `POST /api/billing/invoices/{id}/proof/` |
| `jobs` | 30/heure | utilisateur | `POST /api/jobs/`, `POST /api/jobs/{id}/retry/` |
| `admin_login` | 10/min | IP et identifiant saisi | `POST` sur la page de connexion de l'admin Django (middleware) |

- La portée d'une route se déclare soit dans la vue (`throttle_scope = "..."`, idiome DRF), soit
  dans `ROUTE_SCOPES` (nom d'URL + méthode : lister ses documents ne consomme pas le quota de
  dépôts). Toute portée `X` qui a un taux `X_email` est aussi limitée par adresse e-mail.
- Une réponse 429 porte `{"detail": "Trop de tentatives. Réessayez dans 42 secondes."}` et l'en-tête
  `Retry-After`. Le frontend affiche `detail` tel quel.
- Compteurs : cache Django. En production, `REDIS_URL` doit pointer vers Redis, idéalement une base
  dédiée (`redis://127.0.0.1:6379/2`), sinon chaque worker gunicorn compte de son côté. En dev et
  en test, le cache est en mémoire (`DJANGO_DEV_REDIS_CACHE=True` pour utiliser Redis en dev).
  Si Redis tombe, la limitation est ignorée et un avertissement est journalisé, sans bloquer
  les connexions.
- IP du client : derrière nginx, `DJANGO_NUM_PROXIES=1` (valeur par défaut de `config.settings.prod`).
  Django lit alors la dernière adresse de `X-Forwarded-For`, celle ajoutée par nginx, qu'un client
  ne peut pas falsifier. Derrière un CDN de plus (Cloudflare), il faut 2.
- À surveiller : au Cameroun, beaucoup d'abonnés mobiles partagent la même IP publique (CGNAT).
  Les limites par IP sont larges pour cette raison ; au besoin, ajuster les taux.

## 4. Administration et documentation de l'API

- Chemin de l'admin : `DJANGO_ADMIN_URL` (défaut `admin/`). En production, choisir un chemin
  difficile à deviner (ex. `gestion-7f3k9q/`). `check --deploy` le signale sinon (`core.W001`).
- Connexion à l'admin freinée par IP et par identifiant (`AdminLoginThrottleMiddleware`), en plus
  de `limit_req` dans nginx.
- `/api/docs/` et `/api/schema/` sont réservés au staff : connecté à l'admin Django (session) ou
  avec un jeton `is_staff`. Ils restent ouverts à tous en dev.

## 5. Réglages de production

`config.settings.prod` :
- refuse de démarrer si `DJANGO_SECRET_KEY` est absente, publique (valeurs du dépôt,
  `django-insecure-…`) ou faible (moins de 50 caractères variés) ;
- force `DEBUG = False` quelle que soit `DJANGO_DEBUG` ;
- HSTS 1 an, `MEDIA_X_ACCEL_REDIRECT=True` et `DJANGO_NUM_PROXIES=1` par défaut.

`python manage.py check --deploy` (avec `DJANGO_SETTINGS_MODULE=config.settings.prod`) signale en
plus : admin sur `/admin/` (`core.W001`), cache non partagé (`core.W002`), fichiers envoyés par
Django (`core.W003`) et `DJANGO_NUM_PROXIES` absent (`core.W004`).

## 6. Mise en production (serveur)

Fichiers fournis dans `ops/nginx/` :

| Fichier | Contexte nginx | Rôle |
|---|---|---|
| `presse-zones.conf` | `http` → `/etc/nginx/conf.d/` | zones `limit_req` |
| `presse-security-headers.conf` | inclus | HSTS 1 an, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy |
| `presse-proxy.conf` | inclus | transmission vers gunicorn (127.0.0.1:8097) |
| `presse-hardening.conf` | `server` | en-têtes + CSP de l'appli, `limit_req` sur `/api/auth/` et l'admin, admin sur son chemin secret, CSP assouplie pour `/api/docs/` |
| `presse-media.conf` | `server` | emplacement `internal` `/protected-media/`, `/media/` fermé |

Ordre conseillé :

1. Sauvegarde (base, `.env`, vhost nginx actuel : `nginx -T > /root/backups/nginx-<date>.txt`).
2. `.env` : vérifier `DJANGO_SECRET_KEY`, qui doit faire au moins 50 caractères. Sinon, en générer
   une ; tous les utilisateurs devront alors se reconnecter. Ajouter
   `REDIS_URL=redis://127.0.0.1:6379/2`, `DJANGO_ADMIN_URL=<chemin-secret>/` et
   `DJANGO_NUM_PROXIES=1`.
3. Déployer le code, puis `pip install -r requirements/prod.txt` (`pypdfium2`, déjà présent via
   pdfplumber, est maintenant épinglé) et redémarrer `presse-backend` (`pm2 restart … --update-env`).
4. nginx : copier `presse-zones.conf` dans `/etc/nginx/conf.d/` et les autres fichiers dans
   `/etc/nginx/snippets/presse/`. Remplacer `__ADMIN_PATH__` dans `presse-hardening.conf`. Dans le
   vhost (CloudPanel), **supprimer** les anciens blocs `location /media/` et `location /admin/`,
   puis ajouter `include /etc/nginx/snippets/presse/presse-media.conf;` et
   `include /etc/nginx/snippets/presse/presse-hardening.conf;`.
   Lancer `nginx -t && systemctl reload nginx`.
5. Vérifications :
   - `curl -sI https://presse.mirlab.cloud/` : `content-security-policy`,
     `strict-transport-security: max-age=31536000`.
   - `curl -sI https://presse.mirlab.cloud/media/organizations/x.png` → 404.
   - `curl -sI https://presse.mirlab.cloud/admin/` → 404 ; `/<chemin-secret>/` → 302 vers la connexion.
   - `curl -s https://presse.mirlab.cloud/api/docs/` → 403 sans session staff.
   - Dans l'appli : les aperçus des photos d'une revue s'affichent, et l'export PDF/Word se
     télécharge. La réponse du fichier porte `content-security-policy: … sandbox`.
   - `DJANGO_SETTINGS_MODULE=config.settings.prod venv/bin/python manage.py check --deploy`
     ne doit plus afficher `core.W00x`.
6. Si un `location` existant du vhost (ex. `location /` de l'appli React) déclare ses propres
   `add_header`, il n'hérite plus de ceux du server. Y ajouter alors
   `include /etc/nginx/snippets/presse/presse-security-headers.conf;` et la ligne CSP.
