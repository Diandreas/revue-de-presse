# Déploiement — `ops/deploy/deploy.sh`

Déploie une référence git (branche, tag ou commit) sur le serveur de production
(`presse.mirlab.cloud`). Le script se lance **sur le serveur, en root** (PM2 tourne sous
root) ; il ne contient aucun secret : tout vient du `.env` de l'appli.

```bash
/home/mirlab-presse/htdocs/presse.mirlab.cloud/ops/deploy/deploy.sh main
```

## Ce que fait le script, dans l'ordre

1. Vérifie les prérequis (clone git, `.env`, venv, `rsync`, `pm2`, `npm`), récupère la
   référence (`git fetch`) et l'exporte dans un dossier temporaire (`git archive`).
2. **Sauvegarde `predeploy`** (base + fichiers + `.env`) avec `ops/backup/backup.sh`.
3. Construit le frontend (`npm ci && npm run build`) — ou utilise `FRONTEND_DIST_TARBALL`.
   Jusqu'ici, rien n'a changé en production.
4. Garde un instantané du backend actuel dans `.releases/` (5 derniers).
5. Copie le backend avec `rsync --delete` **sans jamais toucher** à `.env`, `venv/`,
   `mediafiles/` (fichiers clients), `staticfiles/` ; écrit `backend/REVISION` (commit
   déployé, repris par Sentry et les sauvegardes) ; met à jour `ops/`.
6. `pip install -r requirements/prod.txt`, `manage.py check --deploy`, `migrate`,
   `collectstatic` — toujours avec `DJANGO_SETTINGS_MODULE=config.settings.prod`.
7. Bascule le frontend : `dist.new` → `dist` (l'ancien reste dans `dist.old`).
8. `pm2 restart presse-backend presse-celery-worker presse-celery-beat --update-env` + `pm2 save`.
9. Contrôle de santé sur `https://presse.mirlab.cloud/api/health/` (12 essais, 5 s
   d'intervalle) : base, Redis et worker Celery doivent répondre.

En cas d'échec, le script indique l'étape et la procédure de retour arrière (instantané
du backend, `dist.old`, sauvegarde predeploy si une migration pose problème).

## Préparation du serveur (une fois)

```bash
# 1. Outils
apt-get install -y git rsync postgresql-client gnupg
node --version   # Node.js 22 requis pour construire le frontend (sinon FRONTEND_DIST_TARBALL)

# 2. Clone du dépôt, utilisé seulement comme source (jamais servi par nginx)
git clone <url-du-dépôt> /home/mirlab-presse/revue-de-presse.git-src
#    dépôt privé : clé de déploiement en lecture seule (GitHub > Settings > Deploy keys)

# 3. Le .env DOIT fixer le module de settings (les points d'entrée ne retombent plus
#    silencieusement sur les settings de dev) :
grep DJANGO_SETTINGS_MODULE /home/mirlab-presse/htdocs/presse.mirlab.cloud/.env
#    -> DJANGO_SETTINGS_MODULE=config.settings.prod   (l'ajouter sinon)

# 4. Sauvegardes : voir ops/backup/restore.md (phrase de passe, crontab).
```

Le premier déploiement avec ce script copie `ops/` dans le dossier de l'appli ; ensuite,
lancer la version installée : `/home/mirlab-presse/htdocs/presse.mirlab.cloud/ops/deploy/deploy.sh <ref>`.

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_DIR` | `/home/mirlab-presse/htdocs/presse.mirlab.cloud` | racine de l'appli (`.env`, `backend/`, `frontend/dist`) |
| `REPO_DIR` | `/home/mirlab-presse/revue-de-presse.git-src` | clone git utilisé comme source |
| `GIT_REMOTE` | `origin` | remote interrogé par `git fetch` |
| `HEALTH_URL` | `https://presse.mirlab.cloud/api/health/` | contrôle final (127.0.0.1 est refusé par `ALLOWED_HOSTS`) |
| `PM2_APPS` | `presse-backend presse-celery-worker presse-celery-beat` | processus redémarrés |
| `SKIP_BACKUP` | `0` | `1` = pas de sauvegarde predeploy (seulement pour une restauration) |
| `FRONTEND_DIST_TARBALL` | vide | `dist/` déjà construit ailleurs (`tar czf dist.tgz -C frontend/dist .`) |
| `KEEP_RELEASES` | `5` | instantanés du backend conservés dans `.releases/` |

## Serveur sans Node.js

Construire le frontend sur un poste (Node 22) à partir **du même commit**, puis :

```bash
# poste de dev
cd frontend && npm ci && npm run build && tar czf ../dist.tgz -C dist .
scp ../dist.tgz root@<serveur>:/root/dist.tgz
# serveur
FRONTEND_DIST_TARBALL=/root/dist.tgz /home/mirlab-presse/htdocs/presse.mirlab.cloud/ops/deploy/deploy.sh <même-commit>
```

## Retour arrière rapide

Le plus simple : redéployer la révision précédente (affichée à la fin de chaque
déploiement et dans `backend/REVISION` de l'instantané) :

```bash
.../ops/deploy/deploy.sh <révision-précédente>
```

Une migration irréversible ou qui a abîmé des données : restaurer la sauvegarde
`predeploy/` (ops/backup/restore.md, section 3) puis redéployer la révision précédente avec
`SKIP_BACKUP=1`.

## Intégration continue

`.github/workflows/ci.yml` lance à chaque push / pull request : pytest (PostgreSQL + Redis,
export PDF WeasyPrint obligatoire), `makemigrations --check`, `ruff check backend/`, build
et oxlint du frontend, shellcheck des scripts `ops/`. Ne déployer qu'un commit dont la CI
est verte.
