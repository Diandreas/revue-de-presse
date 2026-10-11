"""Wrapper autour du SDK officiel `mistralai`. Toute la logique de parsing JSON /
retry est centralisée ici pour que le reste du pipeline manipule des dicts Python.

`get_mistral_client()` est le seul point d'entrée à utiliser ailleurs dans le code :
il bascule sur `FakeMistralClient` si `MISTRAL_API_KEY` est vide, pour que le pipeline
reste démontrable sans clé réelle (et pour que les tests ne frappent jamais l'API
réseau) — mais seulement là où c'est permis (`MISTRAL_ALLOW_FAKE_CLIENT`, par défaut en
DEBUG) : en production, une clé manquante fait échouer la revue avec un message
d'administrateur au lieu de livrer une revue « [MOCK] » à un client.

Chaque appel réel passe par le limiteur de débit (ratelimit.py) et est journalisé avec
ses jetons (usage.py)."""
import base64
import json
import logging
import re
import time

from django.conf import settings
from pydantic import ValidationError

from .errors import AIUnavailableError, OcrUnavailableError, is_quota_blocked, status_code_of
from .prompts.source_text import unwrap_source
from .ratelimit import acquire_ai_slot
from .usage import OPERATION_JSON, OPERATION_JSON_REPAIR, OPERATION_VISION, record_ai_call

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

    def _chat_complete(self, *, operation=OPERATION_JSON, **kwargs):
        """Appel SDK avec réessai/backoff sur 429.

        Chaque tentative passe d'abord par le limiteur de débit (global + par organisation,
        cf. ratelimit.py), puis est journalisée — jetons, durée, échec éventuel — pour le
        suivi du coût (cf. usage.py)."""
        model = kwargs.get("model") or self.model
        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            acquire_ai_slot()  # hors du try : une saturation remonte telle quelle (relance Celery)
            started = time.monotonic()
            try:
                response = self.client.chat.complete(**kwargs)
            except Exception as exc:  # noqa: BLE001 - le SDK lève des types variés
                record_ai_call(model=model, operation=operation, started=started, error=exc)
                # Un quota à 0 (modèle fermé à l'offre) est permanent : inutile d'attendre.
                if status_code_of(exc) != 429 or is_quota_blocked(exc) or attempt == RATE_LIMIT_MAX_RETRIES:
                    raise
                delay = RATE_LIMIT_BACKOFF_SECONDS[min(attempt, len(RATE_LIMIT_BACKOFF_SECONDS) - 1)]
                logger.warning("Mistral 429 (tentative %s), nouvelle tentative dans %ss.", attempt + 1, delay)
                time.sleep(delay)
                continue
            record_ai_call(model=model, operation=operation, started=started, response=response)
            return response

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
            operation=OPERATION_VISION,
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
                operation=OPERATION_JSON_REPAIR,
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
        "press_entry": lambda: {
            "journal": "JOURNAL (MOCK)",
            "rubrique": "generale",
            "titre": "Titre factice",
            "resume": "[MOCK] Notice factice — configurez MISTRAL_API_KEY pour une vraie revue de presse.",
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
        response = factory()
        if response_hint == "highlight_detection":
            # Les extraits sont vérifiés dans le texte source (grounding.py) : un extrait
            # factice serait écarté. Le mock cite donc la 1re phrase du texte, tel quel ;
            # seule l'explication est factice (et le dit).
            sentence = _first_sentence(unwrap_source(user_prompt))
            if sentence:
                response["highlights"][0].update(
                    excerpt=sentence,
                    explanation="[MOCK] Passage cité tel quel — configurez MISTRAL_API_KEY pour une vraie analyse.",
                )
        return response


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _first_sentence(text, max_chars=200):
    for sentence in _SENTENCE_END.split(" ".join((text or "").split())):
        if len(sentence.split()) >= 4:
            return sentence[:max_chars].rsplit(" ", 1)[0] if len(sentence) > max_chars else sentence
    return ""


def fake_client_allowed():
    """`MISTRAL_ALLOW_FAKE_CLIENT` ; non renseigné = autorisé seulement en DEBUG."""
    allowed = getattr(settings, "MISTRAL_ALLOW_FAKE_CLIENT", None)
    return bool(settings.DEBUG if allowed is None else allowed)


def get_mistral_client():
    if not settings.MISTRAL_API_KEY:
        if not fake_client_allowed():
            raise AIUnavailableError(
                "MISTRAL_API_KEY vide et client factice interdit (MISTRAL_ALLOW_FAKE_CLIENT).",
                user_message=(
                    "Le service d'IA n'est pas configuré sur le serveur (clé Mistral manquante). Ce "
                    "n'est pas un problème de vos fichiers : contactez l'administrateur de la plateforme."
                ),
            )
        logger.info("MISTRAL_API_KEY non configurée : utilisation de FakeMistralClient.")
        return FakeMistralClient()
    return MistralClient()


def complete_structured(client, *, schema, system_prompt, user_prompt, response_hint=None, temperature=None):
    """Appel JSON + validation par `schema`, avec UNE nouvelle tentative corrective si la
    réponse ne respecte pas le format (défaut fréquent des petits modèles).

    Fonctionne avec tout objet exposant `complete_json` (client réel, `FakeMistralClient`,
    faux clients de test)."""
    options = {} if temperature is None else {"temperature": temperature}
    raw = client.complete_json(
        system_prompt=system_prompt, user_prompt=user_prompt, response_hint=response_hint, **options
    )
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
        raw = client.complete_json(
            system_prompt=system_prompt, user_prompt=corrective, response_hint=response_hint, **options
        )
        return schema.model_validate(raw)  # 2e échec : ValidationError, le job échoue proprement
