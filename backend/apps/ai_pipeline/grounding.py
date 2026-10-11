"""Contrôle des points clés avant enregistrement.

Un point clé est cité entre guillemets dans la revue remise à la direction : une citation
inventée ou paraphrasée par l'IA détruit la confiance dès la première revue. Chaque extrait
renvoyé par le modèle est donc :

- **retrouvé dans le texte source** de l'extrait analysé, par une recherche approchée
  tolérante au bruit de l'OCR (accents, ponctuation, césures, quelques lettres mal lues,
  « … » entre deux morceaux de phrase) — sinon il est écarté ;
- écarté s'il est **trop court** ou s'il n'est que le **nom du journal** (« CAMEROON
  TRIBUNE », « LE JOUR N° 3456 du lundi 10 octobre ») ;
- écarté si le modèle lui-même s'en dit **peu sûr** (`HIGHLIGHT_MIN_CONFIDENCE`).

`check_highlight()` renvoie la raison du rejet (tracée dans le résumé de l'étape), ou None.
Recherche approchée : `difflib` (bibliothèque standard), ancrée sur les mots en commun puis
mesurée caractère par caractère sur une fenêtre de même longueur que l'extrait.
"""
import re
from difflib import SequenceMatcher

from django.conf import settings

from . import media

DEFAULT_MIN_CONFIDENCE = 0.5
DEFAULT_MIN_EXCERPT_WORDS = 3
# Calibré sur du texte OCR bruité : une vraie citation (lettres mal lues corrigées par le
# modèle, accents, césures) obtient 0,91 à 1 ; une paraphrase (« a déclaré » pour « a
# annoncé », « l'État » pour « le gouvernement ») 0,76 à 0,86.
DEFAULT_MIN_SIMILARITY = 0.88

REJECT_TOO_SHORT = "too_short"
REJECT_NEWSPAPER_NAME = "newspaper_name"
REJECT_LOW_CONFIDENCE = "low_confidence"
REJECT_NOT_FOUND = "not_found"

# « … », « ... », « [...] », « (…) » : le modèle coupe parfois une longue citation.
_ELLIPSIS = re.compile(r"\[\s*(?:\.{2,}|…)\s*\]|\(\s*(?:\.{2,}|…)\s*\)|\.{3,}|…")
# Mot coupé en fin de ligne par l'OCR : « gouverne-\nment ».
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\r?\n\s*(\w)")
# Marque posée par la lecture des photos sur un passage illisible (cf. TRANSCRIPTION_PROMPT) :
# le modèle ne la recopie pas dans sa citation.
_ILLEGIBLE = re.compile(r"\[\s*illisible\s*\]", re.IGNORECASE)
_MAX_ANCHORS = 25

# Ce qui entoure le nom d'un journal dans un en-tête : numéro, date, périodicité.
_MASTHEAD_NOISE = frozenset(
    "n no num numero nr du de des le la edition parution page p quotidien hebdomadaire journal "
    "lundi mardi mercredi jeudi vendredi samedi dimanche janvier fevrier mars avril mai juin "
    "juillet aout septembre octobre novembre decembre".split()
)


def _setting(name, default):
    value = getattr(settings, name, None)
    return default if value is None else value


def normalized_words(text):
    """Mots en minuscules ASCII, sans ponctuation ni césure (« L'Œil » -> ["l", "oeil"])."""
    return media.plain(_HYPHEN_BREAK.sub(r"\1\2", text or "")).split()


def _ratio(needle, window):
    return SequenceMatcher(None, needle, window, autojunk=False).ratio()


def _segment_similarity(needle_words, source_words):
    """Meilleure ressemblance (0..1) entre le segment et une portion du texte source."""
    needle = " ".join(needle_words)
    if f" {needle} " in f" {' '.join(source_words)} ":
        return 1.0
    size = len(needle_words)
    if size >= len(source_words):
        return _ratio(needle, " ".join(source_words))
    # Ancres : blocs de mots identiques entre l'extrait et le source (les mots très fréquents
    # sont ignorés par difflib, ce qui garde la recherche rapide sur un long extrait).
    blocks = SequenceMatcher(None, needle_words, source_words).get_matching_blocks()[:-1]
    starts = {block.b - block.a for block in sorted(blocks, key=lambda b: -b.size)[:_MAX_ANCHORS]}
    best = 0.0
    for start in starts:
        for shift in (start - 1, start, start + 1):  # un mot ajouté / omis avant l'ancre
            begin = max(0, min(shift, len(source_words) - size))
            for length in (size, size + 1):
                window = " ".join(source_words[begin:begin + length])
                matcher = SequenceMatcher(None, needle, window, autojunk=False)
                if matcher.quick_ratio() > best:
                    best = max(best, matcher.ratio())
        if best >= 0.999:
            break
    return best


def excerpt_similarity(excerpt, source_text):
    """Ressemblance (0..1) entre l'extrait cité et le passage le plus proche du texte source.
    Un extrait coupé par « … » doit voir chacun de ses morceaux retrouvé (le moins bon compte).

    Les chiffres comptent double dans une revue (montants, bilans, dates) : un nombre cité
    qui n'apparaît nulle part dans le texte source suffit à rejeter l'extrait, même si le
    reste de la phrase est identique (« 5 milliards » au lieu de « 2 milliards »)."""
    source_words = normalized_words(_ILLEGIBLE.sub(" ", source_text or ""))
    segments = [words for words in (normalized_words(part) for part in _ELLIPSIS.split(excerpt or "")) if words]
    if not segments or not source_words:
        return 0.0
    source_numbers = {word for word in source_words if word.isdigit()}
    if any(word.isdigit() and word not in source_numbers for words in segments for word in words):
        return 0.0
    if len(segments) > 1:
        # Un fragment d'un ou deux mots autour d'une coupure ne prouve rien à lui seul.
        segments = [words for words in segments if len(words) >= 3] or segments
    return min(_segment_similarity(words, source_words) for words in segments)


def is_newspaper_name(excerpt):
    """Vrai si l'extrait n'est que le nom d'un journal connu, éventuellement suivi de son
    numéro et de sa date (en-tête de la une, pas une information)."""
    words = media.plain(excerpt).split()
    while words and (words[-1].isdigit() or words[-1] in _MASTHEAD_NOISE):
        words.pop()
    while words and words[0] in ("journal", "quotidien", "hebdomadaire"):
        words.pop(0)
    if not words:
        return True  # seulement un numéro / une date
    found = media.identify(" ".join(words))
    return bool(found and found["exact"])


def check_highlight(*, excerpt, confidence, source_text):
    """Raison du rejet d'un point clé (constantes REJECT_*), ou None s'il est conservé.
    Contrôles du moins coûteux au plus coûteux."""
    if len(normalized_words(excerpt)) < int(_setting("HIGHLIGHT_MIN_EXCERPT_WORDS", DEFAULT_MIN_EXCERPT_WORDS)):
        return REJECT_TOO_SHORT
    if is_newspaper_name(excerpt):
        return REJECT_NEWSPAPER_NAME
    # Confiance absente : le modèle ne l'a pas donnée, on ne peut pas en juger — l'extrait
    # reste soumis à la vérification dans le texte.
    if confidence is not None and confidence < float(_setting("HIGHLIGHT_MIN_CONFIDENCE", DEFAULT_MIN_CONFIDENCE)):
        return REJECT_LOW_CONFIDENCE
    if excerpt_similarity(excerpt, source_text) < float(_setting("HIGHLIGHT_EXCERPT_MIN_SIMILARITY", DEFAULT_MIN_SIMILARITY)):
        return REJECT_NOT_FOUND
    return None
