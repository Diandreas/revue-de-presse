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

## Orchestration Celery

`backend/apps/ai_pipeline/tasks.py:run_press_review_pipeline` lance une `chain` Celery
(`task_extract_text → task_chunk_and_summarize → task_detect_highlights → task_draft_review`).
Chaque tâche :

1. fait transitionner le job vers l'étape qu'elle exécute (`transition_job`),
2. exécute le travail,
3. marque l'étape réussie (`mark_step_result`), ou échouée + fait passer le job en
   `FAILED` avant de re-lever l'exception.

Il n'y a pas de `link_error` : une `chain` Celery n'invoque la tâche suivante que sur
succès de la précédente, donc une exception stoppe naturellement la suite — pas besoin
de dépendre de la sémantique (fragile) des callbacks d'erreur Celery.

## Progression

`PressReviewJob.progress_percent` combine deux niveaux :

- un poids fixe par étape (`STEP_WEIGHTS` : extraction 15 %, découpage/résumé 25 %,
  détection 35 %, rédaction 20 %, finalisation 5 %),
- une progression fine **à l'intérieur** de l'étape `HIGHLIGHT_DETECTION` (et
  `CHUNKING_SUMMARIZATION`), recalculée à chaque chunk traité via
  `update_step_progress(job, step, chunks_done, chunks_total)`.

Le frontend interroge `GET /api/jobs/{id}/` toutes les 3 secondes tant que le job est
actif (`frontend/src/features/jobs/useJobs.ts:useJob`) — pas de WebSocket dans cette
première passe ; le payload est conçu pour qu'un push temps réel (Django Channels)
puisse remplacer le polling plus tard sans changer le contrat frontend.

## Extraction & OCR

`backend/apps/ai_pipeline/extraction.py` : `pdfplumber` d'abord (PDF numérique) ; si la
densité de caractères par page est trop faible (coupure de presse scannée), bascule sur
`pdf2image` + `pytesseract` (`lang="fra"`). Le texte extrait est stocké avec des sauts de
page (`\f`) pour permettre à `chunking.py` d'aligner les chunks — et donc les highlights
détectés — sur un numéro de page approximatif.

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
l'API réseau.

## Export

`backend/apps/ai_pipeline/export.py` rend la revue Markdown en PDF (WeasyPrint) et DOCX
(python-docx), mis en cache sur `GeneratedReview` (un même format n'est généré qu'une
fois). Endpoint : `GET /api/jobs/{id}/review/export/?format=pdf|docx`.
