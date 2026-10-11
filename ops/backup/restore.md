# Sauvegardes et restauration — Revue de Presse

Ce qui est sauvegardé chaque nuit par `ops/backup/backup.sh` :

| Élément | Fichier dans l'archive | Pourquoi |
|---|---|---|
| Base PostgreSQL (`pg_dump -Fc`) | `database.dump` | comptes, organisations, abonnements, factures, revues, points clés |
| Fichiers des clients (`backend/mediafiles`) | `mediafiles.tar.gz` | photos et PDF déposés, exports Word/PDF |
| Configuration (`.env`) | `env` | secrets (clé Django, clé Mistral, SMTP…) : sans eux, la base restaurée est inutilisable |
| Informations | `MANIFEST`, `SHA256SUMS` | date, révision déployée, version de pg_dump, sommes de contrôle |

L'archive `revue-de-presse-AAAAMMJJTHHMMSSZ.tar.gpg` est chiffrée (AES-256, GPG symétrique)
avec la phrase de passe de `/root/.config/revue-de-presse/backup.passphrase`.
**Cette phrase de passe doit aussi être conservée HORS du serveur** (gestionnaire de mots
de passe de l'équipe) : si le serveur est perdu, sans elle les copies distantes sont illisibles.

Rétention locale (`/var/backups/revue-de-presse/`) : `daily/` 7 archives, `weekly/` 4
(copie du dimanche), `monthly/` 12 (copie du 1er du mois), `predeploy/` 5 (avant chaque
déploiement). Copie hors serveur avec rclone si `RCLONE_REMOTE` est défini.

---

## 1. Installation (une fois, en root sur le serveur)

```bash
apt-get install -y postgresql-client gnupg rclone   # rclone seulement pour la copie distante
APP=/home/mirlab-presse/htdocs/presse.mirlab.cloud    # ops/ y est copié par ops/deploy/deploy.sh
chmod 700 "$APP/ops/backup/"*.sh
mkdir -p /var/backups/revue-de-presse /root/.config/revue-de-presse
chmod 700 /var/backups/revue-de-presse /root/.config/revue-de-presse

# Phrase de passe : générée une fois, puis COPIÉE dans le gestionnaire de mots de passe de l'équipe.
openssl rand -base64 48 > /root/.config/revue-de-presse/backup.passphrase
chmod 600 /root/.config/revue-de-presse/backup.passphrase
cat /root/.config/revue-de-presse/backup.passphrase   # à recopier hors du serveur, puis effacer l'écran

# Premier essai manuel :
"$APP/ops/backup/backup.sh" daily
ls -lh /var/backups/revue-de-presse/daily/
```

Copie hors serveur (recommandée : un serveur qui brûle emporte aussi ses sauvegardes) :

```bash
rclone config            # créer un remote, ex. « b2-revue » (Backblaze B2, S3, Google Drive…)
rclone mkdir b2-revue:revue-de-presse-backups
# puis, dans la crontab : RCLONE_REMOTE=b2-revue:revue-de-presse-backups
```

Planification : voir `ops/backup/crontab.example` (`crontab -e` en root).
Le script refuse de copier hors serveur une archive non chiffrée (elle contient le `.env`).

## 2. Test de restauration (chaque mois, sans toucher à la production)

Une base jetable est créée une fois pour toutes :

```bash
sudo -u postgres createuser --pwprompt revue_restore          # mot de passe au choix
sudo -u postgres createdb -O revue_restore revue_restore_test
```

Puis (c'est aussi dans `crontab.example`) :

```bash
RESTORE_TEST_DATABASE_URL='postgres://revue_restore:MOTDEPASSE@127.0.0.1:5432/revue_restore_test' \
  /home/mirlab-presse/htdocs/presse.mirlab.cloud/ops/backup/verify-backup.sh
```

Le script déchiffre la dernière archive quotidienne, vérifie les sommes SHA-256, restaure
la base dans `revue_restore_test`, compte les lignes des tables principales et vérifie
l'archive des fichiers. Un nombre de comptes / revues cohérent avec la production = OK.

## 3. Restauration réelle (incident)

> Avant tout : **arrêter les écritures** et **garder une copie de l'état actuel**, même
> abîmé (on peut en avoir besoin pour récupérer des données postérieures à la sauvegarde).

### 3.1 Préparer

```bash
APP=/home/mirlab-presse/htdocs/presse.mirlab.cloud
WORK=$(mktemp -d /root/restore.XXXX)
pm2 stop presse-backend presse-celery-worker presse-celery-beat

# Archive à restaurer : la plus récente, ou une archive predeploy/ (retour avant un déploiement).
ls -lt /var/backups/revue-de-presse/{daily,predeploy}/ | head
ARCHIVE=/var/backups/revue-de-presse/daily/revue-de-presse-AAAAMMJJTHHMMSSZ.tar.gpg
# (serveur perdu : rclone copy b2-revue:revue-de-presse-backups/daily/<archive> /root/)

gpg --batch --pinentry-mode loopback \
    --passphrase-file /root/.config/revue-de-presse/backup.passphrase \
    --decrypt --output "$WORK/backup.tar" "$ARCHIVE"
tar -C "$WORK" -xf "$WORK/backup.tar"
cd "$WORK"/revue-de-presse-*/
sha256sum --check SHA256SUMS          # doit afficher OK pour chaque fichier
cat MANIFEST                          # date et révision du code au moment de la sauvegarde
```

### 3.2 Base de données

```bash
# Copie de sécurité de l'état actuel (même abîmé) :
set -a; . "$APP/.env"; set +a        # ou exporter DATABASE_URL à la main si le .env n'est pas du shell
pg_dump "$DATABASE_URL" -Fc -f "/root/avant-restauration-$(date +%Y%m%d%H%M).dump"

# Restauration (remplace le contenu des tables par celui de la sauvegarde) :
pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error \
    --dbname="$DATABASE_URL" database.dump
```

Base totalement perdue : la recréer d'abord (même nom et même propriétaire que dans
`DATABASE_URL`) : `sudo -u postgres createdb -O <utilisateur> <base>`, puis `pg_restore` ci-dessus.

### 3.3 Fichiers des clients

```bash
mv "$APP/backend/mediafiles" "$APP/backend/mediafiles.avant-restauration" 2>/dev/null || true
tar -C "$APP/backend" -xzf mediafiles.tar.gz --no-same-owner
# Même propriétaire que l'ancien dossier (celui des processus PM2) :
chown -R --reference="$APP/backend/mediafiles.avant-restauration" "$APP/backend/mediafiles" 2>/dev/null || true
```

### 3.4 Configuration (seulement si le `.env` est perdu ou corrompu)

```bash
diff env "$APP/.env" || true          # comparer avant d'écraser
cp env "$APP/.env" && chmod 600 "$APP/.env"
```

### 3.5 Code (si la révision diffère)

`MANIFEST` donne la révision déployée au moment de la sauvegarde. Si le code actuel contient
des migrations plus récentes que la base restaurée, redéployer la révision de la sauvegarde :
`ops/deploy/deploy.sh <révision>` (avec `SKIP_BACKUP=1` pour ne pas sauvegarder l'état cassé
par-dessus), ou laisser `migrate` rejouer les migrations si elles sont compatibles.

### 3.6 Redémarrer et vérifier

```bash
cd "$APP/backend"
DJANGO_SETTINGS_MODULE=config.settings.prod venv/bin/python manage.py migrate --noinput
pm2 restart presse-backend presse-celery-worker presse-celery-beat --update-env
curl -fsS https://presse.mirlab.cloud/api/health/     # {"status": "ok", ...}
```

Puis : se connecter avec un compte client de test, ouvrir une revue, télécharger un
export, vérifier qu'une photo s'affiche. Supprimer `$WORK` une fois tout validé
(`rm -rf "$WORK"`) — il contient le `.env` en clair.

## 4. En cas de doute

- Archive illisible (`gpg: decryption failed`) : mauvaise phrase de passe → reprendre celle
  du gestionnaire de mots de passe.
- `pg_restore: error: unsupported version` : le client `pg_restore` doit être d'une version
  ≥ à celle de `pg_dump` (voir `MANIFEST`).
- Une restauration partielle (une seule organisation) n'est pas prévue par les scripts :
  restaurer dans une base jetable (section 2) puis copier les lignes utiles à la main.
