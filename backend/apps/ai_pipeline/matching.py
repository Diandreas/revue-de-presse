"""Correspondance tolérante entre le nom de catégorie renvoyé par le modèle et les
`DetectionCategory` réellement configurées.

Constaté en réel (ministral-8b) : sur le MÊME texte, le modèle écrit tantôt « Intox
potentielle », tantôt `into_x_potentielle` ou `risque_juridique`. Une correspondance exacte
faisait jeter ces points saillants sans aucun message — la revue paraissait « réussie » avec
des passages sensibles manquants, ce qui est le pire défaut pour un outil de veille juridique.
"""
import difflib
import re
import unicodedata

FUZZY_CUTOFF = 0.78


def _normalize(text):
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[\s_\-]+", " ", ascii_text).strip().lower()


def match_category(name, categories):
    """Retourne la catégorie visée par `name`, ou None si rien de plausible.

    Ordre : nom exact normalisé (casse, accents, `_`/`-`) → code de type (`legal_risk`,
    `intox`… le prompt les affiche) → nom approchant (fautes de frappe, lettres mangées).
    `categories` doit être ordonné (sort_order) : à type égal, la première l'emporte."""
    wanted = _normalize(name)
    if not wanted:
        return None

    by_name = {_normalize(c.name): c for c in categories}
    if wanted in by_name:
        return by_name[wanted]

    by_type = {}
    for category in categories:
        by_type.setdefault(_normalize(category.type), category)
    if wanted in by_type:
        return by_type[wanted]

    close = difflib.get_close_matches(wanted, list(by_name), n=1, cutoff=FUZZY_CUTOFF)
    return by_name[close[0]] if close else None
