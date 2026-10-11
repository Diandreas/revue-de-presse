# Rotation des journaux PM2 (pm2-logrotate)

Sans rotation, les journaux de `presse-backend`, `presse-celery-worker` et
`presse-celery-beat` (`/root/.pm2/logs/*.log`) grossissent jusqu'à remplir le disque — et
un disque plein arrête PostgreSQL, Redis et les sauvegardes en même temps.

## Installation (une fois, en root sur le serveur)

```bash
pm2 install pm2-logrotate

# Un fichier ne dépasse pas 20 Mo, 14 fichiers gardés par journal, anciens fichiers compressés.
pm2 set pm2-logrotate:max_size 20M
pm2 set pm2-logrotate:retain 14
pm2 set pm2-logrotate:compress true
# Rotation quotidienne à minuit en plus de la limite de taille.
pm2 set pm2-logrotate:rotateInterval '0 0 * * *'
pm2 set pm2-logrotate:dateFormat YYYY-MM-DD_HH-mm-ss
pm2 set pm2-logrotate:workerInterval 60

pm2 save
```

Vérifier :

```bash
pm2 conf pm2-logrotate          # affiche les réglages ci-dessus
pm2 ls                          # pm2-logrotate apparaît comme module « online »
ls -lh /root/.pm2/logs/         # fichiers *__AAAA-MM-JJ_*.log.gz après la première rotation
du -sh /root/.pm2/logs/
```

Le module est propre à l'utilisateur qui lance PM2 (ici root) : à refaire si PM2 change
d'utilisateur. Il survit aux redémarrages du serveur tant que `pm2 save` + `pm2 startup` ont
été faits.

## Journal des sauvegardes

`ops/backup/crontab.example` écrit dans `/var/log/revue-de-presse-backup.log` (hors PM2).
Rotation par le logrotate du système — créer `/etc/logrotate.d/revue-de-presse-backup` :

```
/var/log/revue-de-presse-backup.log {
    monthly
    rotate 12
    compress
    missingok
    notifempty
}
```

Tester : `logrotate --debug /etc/logrotate.d/revue-de-presse-backup`.

## Lire les journaux

```bash
pm2 logs presse-backend --lines 200          # requêtes / erreurs Django
pm2 logs presse-celery-worker --lines 200    # pipeline IA, e-mails (« définitivement non envoyé » = échec définitif)
pm2 logs presse-celery-beat --lines 50       # tâches périodiques (rappels, surveillance des jobs bloqués)
```
