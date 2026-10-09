"""Mise en forme « revue de presse » classique au Cameroun, celle que les cellules de
communication diffusent chaque matin : un bandeau « REVUE DE PRESSE — CAMEROUN — date »,
des rubriques (presse générale, économique, régionale…) et, pour chaque journal, son nom
puis un paragraphe qui s'ouvre sur le titre de la une entre guillemets.

La revue est stockée sous forme structurée (`GeneratedReview.structured`) :

    {"format": "press_review_v1", "country": "CAMEROUN", "date_label": "Jeudi 5 mars 2026",
     "sections": [{"key": "generale", "entries": [
         {"source": "CAMEROON TRIBUNE", "headline": "Une volonté de transparence",
          "summary": "Le quotidien gouvernemental ouvre sur…", "documents": ["une.jpg"]}]}]}

Titres, couleurs et pictogrammes des rubriques ne sont PAS stockés : ils sont résolus au
rendu (`present`), pour pouvoir faire évoluer la charte sans régénérer les revues.
"""
import re
import unicodedata

from django.utils import timezone

FORMAT_VERSION = "press_review_v1"

# Ordre d'affichage = ordre de la liste. Couleurs reprises du modèle de revue fourni par
# le client (bandeaux pleine largeur, texte blanc).
RUBRIQUES = [
    {"key": "generale", "title": "LA PRESSE GÉNÉRALE", "color": "#1A237E", "icon": "📰",
     "hint": "quotidiens et hebdomadaires d'information générale"},
    {"key": "economie", "title": "PRESSE ÉCONOMIQUE ET FINANCIÈRE", "color": "#1B5E20", "icon": "💰",
     "hint": "journaux économiques et financiers, entreprises, banques, matières premières"},
    {"key": "regionale", "title": "PRESSE RÉGIONALE, SÉCURITÉ & DIPLOMATIE", "color": "#4A148C", "icon": "🌍",
     "hint": "presse régionale, sécurité, défense, terrorisme, diplomatie, international"},
    {"key": "societe", "title": "SANTÉ, NUMÉRIQUE & SOCIÉTÉ", "color": "#00695C", "icon": "🏥",
     "hint": "santé, numérique, éducation, faits de société"},
    {"key": "politique", "title": "POLITIQUE & VIE INSTITUTIONNELLE", "color": "#BF360C", "icon": "🏛️",
     "hint": "politique, élections, parlement, gouvernement, institutions"},
    {"key": "sport", "title": "SPORTS & CULTURE", "color": "#E65100", "icon": "⚽",
     "hint": "sport, culture, divertissement"},
    {"key": "deces", "title": "DÉCÈS ET HOMMAGES", "color": "#37474F", "icon": "🕊️",
     "hint": "nécrologies, obsèques, hommages"},
]
RUBRIQUE_BY_KEY = {r["key"]: r for r in RUBRIQUES}
DEFAULT_RUBRIQUE = "generale"

# Mots-clés reconnus quand le modèle écrit la rubrique à sa façon (« Économie », « santé »,
# « LA PRESSE REGIONALE »…). Testés dans l'ordre : le plus spécifique d'abord.
_RUBRIQUE_KEYWORDS = [
    ("deces", ("deces", "hommage", "necrolog", "obseque", "deuil")),
    ("economie", ("econom", "financ", "business", "bourse")),
    ("regionale", ("region", "secur", "diplom", "defense", "international", "terror")),
    ("societe", ("sante", "numerique", "societe", "social", "education", "digital")),
    ("politique", ("politi", "institution", "parlement", "election", "gouvern")),
    ("sport", ("sport", "cultur", "divertis")),
    ("generale", ("general", "information")),
]

# Quotidiens / hebdos d'information générale : toujours en « presse générale », quel que
# soit le sujet de leur une (le modèle classe parfois la page par son sujet : un décès en
# une du Guardian Post finissait en « Décès et hommages »).
GENERAL_DAILIES = {
    "cameroon tribune", "le jour", "le messager", "mutations", "la nouvelle expression",
    "emergence", "the guardian post", "the sun", "the post", "le quotidien", "integration",
    "l action", "la voix du centre", "repere", "l anecdote", "le popoli",
}

_COUNTRIES = {
    "CM": "CAMEROUN", "GA": "GABON", "CG": "CONGO", "CD": "RD CONGO", "TD": "TCHAD",
    "CF": "CENTRAFRIQUE", "GQ": "GUINÉE ÉQUATORIALE", "CI": "CÔTE D'IVOIRE", "SN": "SÉNÉGAL",
    "BJ": "BÉNIN", "TG": "TOGO", "BF": "BURKINA FASO", "ML": "MALI", "NE": "NIGER", "FR": "FRANCE",
}
_WEEKDAYS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")
_MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _plain(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_rubrique(value):
    """Clé de rubrique à partir de ce que le modèle a écrit ; rubrique générale par défaut."""
    plain = _plain(value)
    if plain.replace(" ", "_") in RUBRIQUE_BY_KEY:
        return plain.replace(" ", "_")
    for key, keywords in _RUBRIQUE_KEYWORDS:
        if any(keyword in plain for keyword in keywords):
            return key
    return DEFAULT_RUBRIQUE


def country_label(code):
    return _COUNTRIES.get((code or "").upper(), "")


def long_french_date(moment=None):
    """« Jeudi 5 mars 2026 » (indépendant de la locale du serveur)."""
    moment = timezone.localtime(moment or timezone.now())
    day = "1er" if moment.day == 1 else str(moment.day)
    return f"{_WEEKDAYS[moment.weekday()]} {day} {_MONTHS[moment.month - 1]} {moment.year}"


def clean_headline(text):
    """Titre de une sans guillemets parasites : le rendu ajoute ses propres « »."""
    return (text or "").strip().strip("«»\"“”'‘’ ").strip()


def _normalize_source(text):
    return _plain(text)


def plain_text(text):
    """Texte brut : les petits modèles glissent du Markdown (**gras**, puces) malgré la
    consigne ; la revue est diffusée telle quelle (Word, PDF, WhatsApp)."""
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text or "")
    text = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"\1", text)  # *italique*
    text = re.sub(r"^\s*(#+|[-*+•])\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s*\n\s*", " ", text).strip()


def build_structured(*, entries, country="", date_label=""):
    """`entries` : dicts {source, rubrique, headline, summary, documents} dans l'ordre de
    lecture. Toutes les pages d'un même journal sont fusionnées en une seule notice, comme
    dans une revue rédigée à la main ; un journal classé « presse générale » sur l'une de
    ses pages reste en presse générale (le modèle classe parfois une page par son sujet)."""
    notices = []
    by_source = {}
    for entry in entries:
        rubrique = entry.get("rubrique") if entry.get("rubrique") in RUBRIQUE_BY_KEY else DEFAULT_RUBRIQUE
        summary = plain_text(entry.get("summary"))
        source_key = _normalize_source(entry.get("source"))
        if source_key in GENERAL_DAILIES:
            rubrique = DEFAULT_RUBRIQUE
        existing = by_source.get(source_key) if source_key else None
        if existing is not None:
            existing["summary"] = f"{existing['summary']} {summary}".strip()
            existing["headline"] = existing["headline"] or clean_headline(plain_text(entry.get("headline")))
            existing["documents"] = existing["documents"] + list(entry.get("documents", []))
            if rubrique == DEFAULT_RUBRIQUE:
                existing["rubrique"] = DEFAULT_RUBRIQUE
            continue
        notice = {
            "rubrique": rubrique,
            "source": (entry.get("source") or "").strip(),
            "headline": clean_headline(plain_text(entry.get("headline"))),
            "summary": summary,
            "documents": list(entry.get("documents", [])),
        }
        notices.append(notice)
        if source_key:
            by_source[source_key] = notice

    by_section = {r["key"]: [] for r in RUBRIQUES}
    for notice in notices:
        by_section[notice.pop("rubrique")].append(notice)
    return {
        "format": FORMAT_VERSION,
        "country": country,
        "date_label": date_label,
        "sections": [{"key": r["key"], "entries": by_section[r["key"]]} for r in RUBRIQUES if by_section[r["key"]]],
    }


def present(structured):
    """Version prête à afficher : rubriques résolues (titre, couleur, pictogramme)."""
    if not structured or structured.get("format") != FORMAT_VERSION:
        return None
    sections = []
    for section in structured.get("sections", []):
        rubrique = RUBRIQUE_BY_KEY.get(section.get("key"), RUBRIQUE_BY_KEY[DEFAULT_RUBRIQUE])
        sections.append(
            {
                "key": rubrique["key"],
                "title": rubrique["title"],
                "color": rubrique["color"],
                "icon": rubrique["icon"],
                "entries": section.get("entries", []),
            }
        )
    return {
        "country": structured.get("country", ""),
        "date_label": structured.get("date_label", ""),
        "sections": sections,
    }


def entry_paragraph(entry):
    """Paragraphe d'une notice : « Titre de la une » — résumé."""
    headline = clean_headline(entry.get("headline"))
    summary = (entry.get("summary") or "").strip()
    if headline and summary:
        return f"« {headline} » — {summary}"
    return summary or (f"« {headline} »" if headline else "")


def to_markdown(structured):
    """Texte de la revue (copier-coller, anciennes interfaces) au même format."""
    view = present(structured)
    if view is None:
        return ""
    masthead = " — ".join(part for part in ("REVUE DE PRESSE", view["country"], view["date_label"]) if part)
    lines = [f"# {masthead}", ""]
    for section in view["sections"]:
        lines += [f"## {section['icon']} {section['title']}", ""]
        for entry in section["entries"]:
            lines += [f"### ▶ {entry['source']}", "", entry_paragraph(entry), ""]
    return "\n".join(lines).strip() + "\n"
