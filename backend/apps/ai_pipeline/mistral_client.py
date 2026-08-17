"""Wrapper autour du SDK officiel `mistralai`. Toute la logique de parsing JSON /
retry est centralisée ici pour que le reste du pipeline manipule des dicts Python.

`get_mistral_client()` est le seul point d'entrée à utiliser ailleurs dans le code :
il bascule automatiquement sur `FakeMistralClient` si `MISTRAL_API_KEY` est vide,
pour que le pipeline reste démontrable sans clé réelle (et pour que les tests ne
frappent jamais l'API réseau)."""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class MistralClient:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or settings.MISTRAL_API_KEY
        self.model = model or settings.MISTRAL_MODEL
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from mistralai import Mistral

            self._client = Mistral(api_key=self.api_key)
        return self._client

    def complete_json(self, *, system_prompt, user_prompt, response_hint=None, temperature=0.2):
        response = self.client.chat.complete(
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

    def _parse_json(self, content):
        try:
            return json.loads(content)
        except (TypeError, json.JSONDecodeError):
            logger.warning("Réponse Mistral non-JSON, tentative de correction.")
            fixed = self.client.chat.complete(
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
