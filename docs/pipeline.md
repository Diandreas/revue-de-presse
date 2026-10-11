# Pipeline de génération de revue de presse

## Machine à états

```
UPLOADED → TEXT_EXTRACTION → CHUNKING_SUMMARIZATION → HIGHLIGHT_DETECTION → REVIEW_DRAFTING → REVIEW_READY → EXPORTED
                    ↘________________________↘____________________↘_______________↘
                                                FAILED (retry possible → TEXT_EXTRACTION)
```

Transitions centralisées et validées dans
`backend/apps/press_review/services/pipeline.py:transition_job` (dict `ALLOWED_TRANSITIONS`).
Rien d'autre ne doit écrire directement `PressReviewJob.status`.

## Exécution en arrière-plan (Celery)

`POST /api/jobs/` **ne fait pas l'analyse** : il crée le job, met la `chain` en file
d'attente (`run_press_review_pipeline`) et répond aussitôt avec `status=UPLOADED`
(~0,15 s mesuré, quelle que soit la taille des fichiers). Un **worker Celery** exécute
ensuite `task_extract_text → task_chunk_and_summarize → task_detect_highlights →
task_draft_review` ; l'interface suit l'avancement par polling et l'utilisateur peut
fermer la page (l'analyse continue, la revue apparaît dans « Revues de presse »).

Chaque tâche :

1. fait entrer le job dans son étape (`enter_step`, **idempotent** : Celery peut rejouer
   une étape sans provoquer de transition invalide),
2. exécute le travail en publiant sa progression (`update_step_progress`),
3. marque l'étape réussie (`mark_step_result`), ou échouée + fait passer le job en
   `FAILED` avant de re-lever l'exception.

Il n'y a pas de `link_error` : une `chain` Celery n'invoque la tâche suivante que sur
succès de la précédente, donc une exception stoppe naturellement la suite.

### Erreurs : ce qui est relancé, ce qui échoue

| Situation | Comportement |
|---|---|
| **Quota à 0** (429 avec `x-ratelimit-limit-req-minute: 0` : modèle fermé à l'offre du compte) | **Pas de relance** (permanent) : job `FAILED` avec un message d'administrateur (changer `MISTRAL_MODEL` / `MISTRAL_VISION_MODEL` ou d'offre). |
| Rate limit Mistral (429), 5xx, timeout réseau | **Relance automatique** de l'étape (45 s, 90 s, 135 s ; 3 relances max). L'interface affiche la pause (`result_summary.retry`). Aucun clic requis. |
| Erreur définitive (403 offre Mistral, 401 clé invalide, données invalides…) | Job `FAILED` tout de suite, message lisible (`ai_pipeline/errors.py:describe_error`), bouton **Réessayer**. |
| Une photo/un fichier illisible ou sans texte | Le **document** est marqué `failed` (+ `extraction_error`), le job continue avec les autres. Il n'échoue que si *aucun* document n'est exploitable. |
| **OCR indisponible sur le serveur** (Tesseract, données `fra`, Poppler) | Job `FAILED` avec un message d'administrateur ; les fichiers ne sont **pas** accusés (`OcrUnavailableError`). Ne jamais avaler cette erreur : elle donnerait des revues vides. |
| Broker injoignable à la mise en file | Job `FAILED` immédiatement (`mark_dispatch_failed`) au lieu de rester bloqué à `UPLOADED`. |
| Worker qui meurt en cours de route | `task_acks_late` : la tâche est rejouée (étapes idempotentes). Limites de temps : 15 min (soft) / 20 min (hard). |

Pas de relance en mode `EAGER` (dev/tests sans worker) : personne n'y honorerait le délai.

### Lancer un vrai worker

- **Docker** : `docker compose up` démarre `celery_worker` + `redis` (voir `docker-compose.yml`).
- **Sans Docker ni Redis** (dev Windows) — broker fichier + pool `solo` :

  ```bash
  # terminal 1 — serveur web (pas d'EAGER)
  CELERY_BROKER_URL=filesystem:// CELERY_TASK_ALWAYS_EAGER=False python manage.py runserver 127.0.0.1:8000
  # terminal 2 — worker
  CELERY_BROKER_URL=filesystem:// CELERY_TASK_ALWAYS_EAGER=False python -m celery -A config worker -l info -P solo
  ```

  (`pip install pywin32` requis sous Windows : déjà dans `requirements/dev.txt`.)
- **Piège** : Celery lit `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` **directement dans
  l'environnement, avec priorité sur les settings Django** — et le `.env` les y injecte
  (hôte Docker `redis`). Voilà pourquoi `settings/test.py` et le mode `filesystem://` de
  `settings/base.py` forcent aussi `os.environ`.
- Sous Windows, préférez `127.0.0.1` à `localhost` : `localhost` ajoute ~2 s par connexion
  (repli IPv6).

`tests/test_background_pipeline.py` inclut des tests avec un **vrai worker** (thread +
broker mémoire) : exécution hors requête, relance automatique jusqu'au succès, abandon
après le nombre max de tentatives.

## Progression

`PressReviewJob.progress_percent` combine deux niveaux :

- un poids fixe par étape (`STEP_WEIGHTS` : extraction 15 %, découpage/résumé 25 %,
  détection 35 %, rédaction 20 %, finalisation 5 %),
- une progression fine **à l'intérieur** de chaque étape, recalculée à chaque unité
  traitée via `update_step_progress(job, step, chunks_done, chunks_total)` : un
  **document** à l'extraction (`3/5 documents`, `result_summary.unit`), un extrait
  ensuite. Les documents sont lus dans l'**ordre d'upload**.

Le frontend interroge `GET /api/jobs/{id}/` toutes les 3 secondes tant que le job est
actif (`frontend/src/features/jobs/useJobs.ts:useJob`) — pas de WebSocket dans cette
première passe ; le payload est conçu pour qu'un push temps réel (Django Channels)
puisse remplacer le polling plus tard sans changer le contrat frontend.

## Extraction & OCR

`backend/apps/ai_pipeline/extraction.py`, aiguillage selon `SourceDocument.kind` :

- **PDF** (`extract_text_from_pdf`) : `pdfplumber` d'abord (PDF numérique : gratuit, instantané,
  exact) ; si la densité de caractères par page est trop faible (coupure de presse scannée),
  chaque page est rendue en image (Poppler) puis lue par le moteur d'OCR configuré.
- **Image / photo** (`extract_text_from_image`) : orientation EXIF corrigée, puis lecture par
  le moteur d'OCR configuré ; `pillow-heif` gère les photos iPhone HEIC/HEIF.
  `page_count=1`, `requires_ocr=True`.

### Moteur de lecture des photos (`OCR_ENGINE`, `apps/ai_pipeline/ocr.py`)

| Valeur | Fonctionnement |
|---|---|
| `auto` (défaut) | `mistral` si `MISTRAL_API_KEY` est renseignée, sinon `tesseract`. |
| `mistral` | **Un modèle de vision de Mistral lit l'image côté serveur** (`MISTRAL_VISION_MODEL`, défaut `ministral-8b-latest`). Aucune dépendance système. Mesuré : 99,5–100 % de fidélité sur une photo de journal tournée et floutée, ~3–5 s par photo. Réglage strict (température 0, « transcris exactement, ne corrige/résume rien, `[illisible]` si besoin »). |
| `tesseract` | OCR local (binaire + données `fra`, Poppler pour les PDF scannés) : hors ligne, mais lecture nettement moins bonne des photos. |

À savoir :
- Les images sont envoyées à Mistral — le **même prestataire** que l'analyse du texte, donc pas
  de nouveau tiers. Pour une contrainte « rien ne sort du serveur », utilisez `tesseract`.
- Un modèle de vision transcrit ; il peut de façon rare se tromper sur un mot. Chaque point
  saillant garde son document source et sa page : une citation doit se vérifier sur l'original.
- **L'API OCR dédiée de Mistral (`mistral-ocr-latest`) n'est pas utilisée** : sur l'offre
  gratuite testée elle répond 429 avec `x-ratelimit-limit-req-minute: 0` (quota nul).
- Poppler reste nécessaire pour lire les **PDF scannés** (rendu des pages en images), quel
  que soit le moteur.

Le texte extrait est stocké avec des sauts de page (`\f`) pour permettre à `chunking.py`
d'aligner les chunks — et donc les highlights détectés — sur un numéro de page approximatif.

`task_extract_text` est résilient par document : une photo illisible / un fichier corrompu
est marqué `extraction_status=failed` et le pipeline continue avec les autres ; le job
n'échoue globalement que si **aucun** document n'a pu être extrait. Un document déjà lu n'est
**jamais relu** lors d'une relance (chaque lecture par l'API est facturée et limitée).

## Découpage et catégories de détection

`backend/apps/ai_pipeline/chunking.py` découpe les documents longs (~6000 tokens/chunk,
aligné sur les pages). Pour chaque chunk, `apps/ai_pipeline/prompts/highlight_detection.py`
injecte la liste des `DetectionCategory` actives (org-scopées + globales) — c'est **l'unique
point d'entrée** du contenu "critères légaux/intox" dans les prompts Mistral : aucun texte
de loi n'est codé en dur, tout est éditable via `/admin/` (voir
[env-and-credentials.md](env-and-credentials.md) et `apps/press_review/admin.py`).

## Mistral

`backend/apps/ai_pipeline/mistral_client.py:get_mistral_client()` bascule automatiquement
sur `FakeMistralClient` (sortie factice labellisée `[MOCK]`) si `MISTRAL_API_KEY` est
vide — le pipeline reste démontrable sans clé réelle, et les tests n'appellent jamais
l'API réseau. Hors DEBUG, ce repli n'est permis que si `MISTRAL_ALLOW_FAKE_CLIENT=true` :
sinon la revue échoue avec un message d'administrateur (`AIUnavailableError`) et
`manage.py check` avertit (`ai_pipeline.W001`).

### Fiabilité et coût (`apps/ai_pipeline`)

- **Points clés ancrés** (`grounding.py`) : chaque extrait est recherché (approché, tolérant
  au bruit OCR) dans le texte de l'extrait analysé ; sont écartés les extraits introuvables,
  trop courts, réduits au nom d'un journal, ou de confiance < `HIGHLIGHT_MIN_CONFIDENCE`. Les
  écarts sont comptés dans `result_summary.discarded_highlights` de l'étape. Détection sur
  `MISTRAL_HIGHLIGHT_MODEL` (ministral-14b) à `HIGHLIGHT_TEMPERATURE` (0).
- **Journal du point clé** (`attribution.py`) : l'annexe PDF/Word et le champ `source_name`
  de `GET /api/jobs/{id}/highlights/` citent le journal (notices de la revue) au lieu du
  nom du fichier.
- **Injection de consignes** (`prompts/source_text.py`) : le texte des documents est placé
  entre `<<<DEBUT_TEXTE_SOURCE>>>` et `<<<FIN_TEXTE_SOURCE>>>`, et chaque prompt système
  demande d'ignorer toute consigne qui s'y trouverait.
- **Mesure** (`usage.py`, modèle `AIUsage`) : chaque appel SDK (organisation, revue, étape,
  modèle, jetons, durée, échec) ; admin « Appels IA » + « Totaux mensuels par organisation ».
- **Limiteur de débit** (`ratelimit.py`) : compteurs par minute global et par organisation
  dans le cache Django (Redis en prod) ; au-delà de `AI_RATE_LIMIT_MAX_WAIT_SECONDS`,
  l'étape est relancée par Celery comme sur un 429.
- **Plafonds** (`limits.py`) : documents et pages par revue selon la formule
  (`AI_REVIEW_LIMITS`), pages max d'un PDF (`AI_MAX_PDF_PAGES`), refus clair à la création.
- **Gros PDF** : rendu et OCR page par page (`ocr.iter_pdf_page_images`), progression
  mémorisée sur le document ; une relance ne relit pas les pages déjà lues.
- **Relances économes** : résumés (`summary_cache`) et réponses de détection
  (`detection_cache`) sont mis en cache par empreinte de prompt dans le résultat de l'étape.

## Export

`backend/apps/ai_pipeline/export.py` rend la revue Markdown en PDF (WeasyPrint) et DOCX
(python-docx), mis en cache sur `GeneratedReview` (un même format n'est généré qu'une
fois). Endpoint : `GET /api/jobs/{id}/review/export/?export_format=pdf|docx` (le paramètre
s'appelle `export_format` : `format` est réservé par la négociation de contenu de DRF).
