"""Schémas pydantic validant les réponses JSON de Mistral avant toute écriture en base.

Volontairement *tolérants* sur la forme : les modèles compacts (Ministral, Nemo…) renvoient
souvent une liste de phrases ou un objet là où on attend une chaîne (constaté en réel : 4
modèles sur 4 sur le prompt de résumé). Plutôt que de faire échouer toute la revue pour un
détail de forme, on normalise ; seule une valeur *vide* est rejetée (déclenche la nouvelle
tentative corrective de `mistral_client.complete_structured`)."""
from typing import ClassVar, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _to_text(value, sep=" "):
    """Aplatit chaîne / liste / objet imbriqué en une seule chaîne."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            text = _to_text(item, sep)
            if text:
                parts.append(f"{key} : {text}")
        return sep.join(parts)
    if isinstance(value, (list, tuple)):
        return sep.join(t for t in (_to_text(v, sep) for v in value) if t)
    return str(value).strip()


def _to_confidence(value):
    """Nombre entre 0 et 1, ou None. Accepte « 0.8 », « 80% », 80 (échelle 0-100)."""
    if value is None or value == "":
        return None
    try:
        number = float(str(value).strip().rstrip("%").replace(",", "."))
    except ValueError:
        return None
    if number > 1:
        number /= 100
    return max(0.0, min(1.0, number))


def _unwrap_root(data, key):
    """Ramène la racine à `{key: valeur}` quelle que soit l'enveloppe choisie par le modèle :
    `{"key": v}` (attendu), `v` nu (liste / texte), ou `[{"key": v}]` (objet correct mais
    enveloppé dans une liste — constaté en réel avec ministral-8b)."""
    if isinstance(data, list):
        wrappers = [item for item in data if isinstance(item, dict) and key in item]
        if wrappers and len(wrappers) == len(data):
            merged = []
            for wrapper in wrappers:
                value = wrapper[key]
                merged.extend(value if isinstance(value, list) else [value])
            return {key: merged}
        return {key: data}
    if isinstance(data, str):
        return {key: data}
    return data


class _BareValueAllowed(BaseModel):
    """Certains modèles renvoient directement la valeur (une liste, un texte) au lieu de
    l'objet `{"<champ>": valeur}` attendu — constaté en réel : une liste de points saillants
    à la racine du JSON, y compris à la relance corrective. Le contenu est bon : on l'emballe."""

    MAIN_FIELD: ClassVar[str]

    @model_validator(mode="before")
    @classmethod
    def _wrap_bare_value(cls, data):
        return _unwrap_root(data, cls.MAIN_FIELD)


class ChunkSummaryResult(_BareValueAllowed):
    MAIN_FIELD = "summary"
    summary: str = Field(min_length=1)

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary(cls, value):
        return _to_text(value, " ")


class HighlightItem(BaseModel):
    category_name: str
    excerpt: str = Field(min_length=1)
    explanation: str = ""
    confidence: Optional[float] = None

    @field_validator("category_name", mode="before")
    @classmethod
    def _coerce_category(cls, value):
        return _to_text(value)

    @field_validator("excerpt", "explanation", mode="before")
    @classmethod
    def _coerce_text(cls, value):
        return _to_text(value, " ")

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value):
        return _to_confidence(value)


class HighlightDetectionResult(_BareValueAllowed):
    MAIN_FIELD = "highlights"
    highlights: list[HighlightItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _find_the_list(cls, data):
        # Clé de liste inattendue (« points_saillants », « results »…) : s'il n'y a qu'une
        # liste dans l'objet, c'est elle.
        if isinstance(data, dict) and "highlights" not in data:
            lists = [v for v in data.values() if isinstance(v, list)]
            if len(lists) == 1:
                return {"highlights": lists[0]}
        return data

    @field_validator("highlights", mode="before")
    @classmethod
    def _coerce_highlights(cls, value):
        if value is None:
            return []
        if isinstance(value, dict):  # un seul extrait renvoyé sans liste
            value = [value]
        if not isinstance(value, list):
            return value
        # Un élément sans extrait (« excerpt »: "" — constaté en réel sur une revue de 27
        # photos) ne surligne rien : on l'écarte au lieu de rejeter toute la réponse, ce
        # qui faisait échouer la revue entière à chaque nouvelle tentative.
        return [item for item in value if not isinstance(item, dict) or _to_text(item.get("excerpt"), " ")]


class ReviewDraftResult(_BareValueAllowed):
    MAIN_FIELD = "summary_markdown"
    summary_markdown: str = Field(min_length=1)

    @field_validator("summary_markdown", mode="before")
    @classmethod
    def _coerce_markdown(cls, value):
        return _to_text(value, "\n\n")
