"""Wrapper autour du SDK officiel `mistralai`. Toute la logique de parsing JSON /
retry est centralisée ici pour que le reste du pipeline manipule des dicts Python.

`get_mistral_client()` est le seul point d'entrée à utiliser ailleurs dans le code :
il bascule automatiquement sur `FakeMistralClient` si `MISTRAL_API_KEY` est vide,
pour que le pipeline reste démontrable sans clé réelle (et pour que les tests ne
frappent jamais l'API réseau)."""
import base64
import json
import logging
import re
import time

from django.conf import settings
from pydantic import ValidationError

from .errors import OcrUnavailableError, is_quota_blocked, status_code_of

logger = logging.getLogger(__name__)

# Réessais internes sur 429 (rate limit) : Mistral throttle beaucoup les paliers bas.
# Backoff court pour absorber un pic sans consommer un cycle de retry Celery entier.
# Si la limite persiste, la tâche Celery est relancée plus tard (voir tasks.py).
RATE_LIMIT_MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_SECONDS = (2, 5, 12)

# Un appel qui pend ne doit jamais bloquer un worker indéfiniment.
REQUEST_TIMEOUT_MS = 120_000

# Lecture d'une photo / d'un scan de coupure de presse par le modèle de vision. Température
# 0 et consigne stricte : dans ce produit une citation doit rester fidèle à l'original
# (contexte juridique / détection d'intox), le modèle ne doit ni « corriger » ni résumer.
TRANSCRIPTION_PROMPT = (
    "Tu es un moteur d'OCR. Transcris EXACTEMENT le texte visible sur cette photo ou ce scan de "
    "coupure de presse, mot pour mot, dans l'ordre de lecture (titre, puis colonnes de gauche à "
    "droite). Ne corrige rien, ne résume pas, n'ajoute aucun commentaire ni mise en forme "
    "Markdown. Si un passage est illisible, écris [illisible]. Si l'image ne contient aucun "
    "texte, réponds exactement : [aucun texte]"
)
NO_TEXT_MARKER = "[aucun texte]"
_CODE_FENCE = re.compile(r"^```[a-zA-Z]*[ \t]*\r?\n(.*?)\r?\n?```[ \t]*$", re.DOTALL)


def _clean_transcription(text):
    text = (text or "").strip()
    fenced = _CODE_FENCE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    if text.lower().strip(" .") == NO_TEXT_MARKER:
        return ""  # -> le document sera signalé « aucun texte lisible »
    return text


class MistralClient:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or settings.MISTRAL_API_KEY
        self.model = model or settings.MISTRAL_MODEL
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from mistralai import Mistral

            self._client = Mistral(api_key=self.api_key, timeout_ms=REQUEST_TIMEOUT_MS)
        return self._client

    def _chat_complete(self, **kwargs):
        """Appel SDK avec réessai/backoff sur 429."""
        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            try:
                return self.client.chat.complete(**kwargs)
            except Exception as exc:  # noqa: BLE001 - le SDK lève des types variés
                # Un quota à 0 (modèle fermé à l'offre) est permanent : inutile d'attendre.
                if status_code_of(exc) != 429 or is_quota_blocked(exc) or attempt == RATE_LIMIT_MAX_RETRIES:
                    raise
                delay = RATE_LIMIT_BACKOFF_SECONDS[min(attempt, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)]
                logger.warning("Mistral 429 (tentative %s), nouvelle tentative dans %ss.", attempt + 1, delay)
                time.sleep(delay)

    def complete_json(self, *, system_prompt, user_prompt, response_hint=None, temperature=0.2):
        response = self._chat_complete(
            model=self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        return self._parse_json(content)

    def transcribe_image(self, jpeg_bytes, *, model=None):
        """Transcrit une image (JPEG) en texte via un modèle de vision de Mistral. Renvoie
        "" si le modèle déclare qu'il n'y a aucun texte."""
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")
        response = self._chat_complete(
            model=model or settings.MISTRAL_VISION_MODEL,
            temperature=0,
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": TRANSCRIPTION_PROMPT},
                        {"type": "image_url", "image_url": data_url},
                    ],
                }
            ],
        )
        return _clean_transcription(response.choices[0].message.content)

    def _parse_json(self, content):
        try:
            return json.loads(content)
        except (TypeError, json.JSONDecodeError):
            logger.warning("Réponse Mistral non-JSON, tentative de correction.")
            fixed = self._chat_complete(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "Tu corriges du JSON invalide. Réponds uniquement avec le JSON corrigé, sans commentaire.",
                    },
                    {"role": "user", "content": str(content)},
                ],
            )
            return json.loads(fixed.choices[0].message.content)


class FakeMistralClient(MistralClient):
    """Sortie factice mais structurellement valide, clairement labellisée [MOCK].
    Utilisée automatiquement si MISTRAL_API_KEY est vide, et systématiquement en tests."""

    _MOCK_RESPONSES = {
        "chunk_summary": lambda: {
            "summary": "[MOCK] Résumé factice — configurez MISTRAL_API_KEY pour une vraie analyse."
        },
        "highlight_detection": lambda: {
            "highlights": [
                {
                    "category_name": "Point important",
                    "excerpt": "[MOCK] Extrait factice — configurez MISTRAL_API_KEY pour une vraie analyse.",
                    "explanation": "Sortie générée par FakeMistralClient (aucun appel réel à Mistral).",
                    "confidence": 0.5,
                }
            ]
        },
        "review_drafting": lambda: {
            "summary_markdown": (
                "# Revue de presse (MOCK)\n\n"
                "Ceci est une revue factice générée par FakeMistralClient car "
                "`MISTRAL_API_KEY` n'est pas configurée. Configurez cette variable "
                "d'environnement pour obtenir une véritable revue générée par l'IA."
            )
        },
    }

    def __init__(self, api_key=None, model=None):
        super().__init__(api_key=api_key or "fake", model=model or "fake-mistral")

    def transcribe_image(self, jpeg_bytes, *, model=None):
        # Surtout pas de « fausse » transcription : elle passerait pour le vrai contenu
        # d'une vraie photo de client.
        raise OcrUnavailableError("Lecture des photos par Mistral impossible : MISTRAL_API_KEY non configurée.")

    def complete_json(self, *, system_prompt, user_prompt, response_hint=None, temperature=0.2):
        factory = self._MOCK_RESPONSES.get(response_hint)
        if factory is None:
            return {"detail": "[MOCK] Réponse factice générique — configurez MISTRAL_API_KEY."}
        return factory()


def get_mistral_client():
    if not settings.MISTRAL_API_KEY:
        logger.info("MISTRAL_API_KEY non configurée : utilisation de FakeMistralClient.")
        return FakeMistralClient()
    return MistralClient()


def complete_structured(client, *, schema, system_prompt, user_prompt, response_hint=None):
    """Appel JSON + validation par `schema`, avec UNE nouvelle tentative corrective si la
    réponse ne respecte pas le format (défaut fréquent des petits modèles).

    Fonctionne avec tout objet exposant `complete_json` (client réel, `FakeMistralClient`,
    faux clients de test)."""
    raw = client.complete_json(system_prompt=system_prompt, user_prompt=user_prompt, response_hint=response_hint)
    try:
        return schema.model_validate(raw)
    except ValidationError as exc:
        logger.warning("Réponse IA au mauvais format (%s) : nouvelle tentative corrective.", response_hint)
        problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:3])
        corrective = (
            f"{user_prompt}\n\nATTENTION : ta réponse précédente ne respectait pas le format JSON "
            f"demandé ({problems}). Réponds à nouveau avec EXACTEMENT le format demandé, sans "
            "aucun texte en dehors du JSON."
        )
        raw = client.complete_json(system_prompt=system_prompt, user_prompt=corrective, response_hint=response_hint)
        return schema.model_validate(raw)  # 2e échec : ValidationError, le job échoue proprement
