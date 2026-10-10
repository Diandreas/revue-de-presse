"""Journaux connus du paysage camerounais, classés du plus lu / plus fiable au moins connu.

Dans une revue de presse rédigée à la main, la cellule de communication ne suit pas l'ordre
dans lequel les pages ont été photographiées : elle commence par les grands quotidiens
nationaux. `rank()` donne ce classement (rubrique par rubrique, cf. press_format.present) ;
les journaux absents de la liste viennent après, dans l'ordre de lecture, et une page dont
le journal n'a pas été identifié ferme la rubrique.

L'ordre de la presse générale reprend celui du modèle de revue fourni par le client
(Cameroon Tribune, Le Jour, Le Messager, Mutations, La Nouvelle Expression, Emergence,
The Guardian Post, The Sun). La liste sert aussi à :
- corriger un nom mal lu sur la photo (« L'OCIL DU SAHEL » -> « L'ŒIL DU SAHEL ») ;
- ranger un journal dans sa rubrique quel que soit le sujet de sa une (un quotidien
  d'information générale reste en presse générale, un titre économique en presse économique).
"""
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

# (nom affiché, rubrique imposée ou None, autres graphies). L'ordre de la liste EST le
# classement : à modifier ici pour faire monter ou descendre un titre.
KNOWN_MEDIA = [
    # Grands quotidiens et hebdomadaires nationaux d'information générale
    ("CAMEROON TRIBUNE", "generale", ("cameroun tribune",)),
    ("LE JOUR", "generale", ("quotidien le jour",)),
    ("LE MESSAGER", "generale", ("messager",)),
    ("MUTATIONS", "generale", ("quotidien mutations",)),
    ("LA NOUVELLE EXPRESSION", "generale", ("nouvelle expression",)),
    ("EMERGENCE", "generale", ()),
    ("THE GUARDIAN POST", "generale", ("guardian post",)),
    ("THE POST", "generale", ()),
    ("THE SUN", "generale", ()),
    ("INTÉGRATION", "generale", ("journal integration",)),
    ("REPÈRES", "generale", ("repere",)),
    ("L'EFFORT CAMEROUNAIS", "generale", ("effort camerounais",)),
    # Presse économique et financière
    ("LE QUOTIDIEN DE L'ÉCONOMIE", "economie", ("quotidien de l economie",)),
    ("INVESTIR AU CAMEROUN", "economie", ()),
    ("ECOMATIN", "economie", ("eco matin",)),
    ("LE FINANCIER D'AFRIQUE", "economie", ("financier d afrique",)),
    ("DÉFIS ACTUELS", "economie", ()),
    ("CONJONCTURE ÉCONOMIQUE", "economie", ()),
    ("EXPRESSION ÉCONOMIQUE", "economie", ()),
    # Presse régionale et spécialisée
    ("L'ŒIL DU SAHEL", "regionale", ("oeil du sahel",)),
    ("KALARA", None, ()),
    ("ECHOS SANTÉ", "societe", ()),
    ("INFOS + SANTÉ", "societe", ("infos sante", "info sante")),
    ("ECHOS DU PARLEMENT", "politique", ()),
    ("L'ACTION", "generale", ()),
    ("LA VOIX DU CENTRE", "generale", ()),
    # Autres titres suivis dans les revues du client
    ("LA LUNE", None, ()),
    ("LE DÉTECTIVE", None, ()),
    ("DIRECT INFO", None, ()),
    ("E-INVESTIGATION", None, ()),
    ("LE TÉMOIN", None, ()),
    ("L'ALBATROS", None, ()),
    ("LA LANTERNE", None, ()),
    # Presse à sensation et satirique
    ("L'ANECDOTE", "generale", ()),
    ("LE POPOLI", "generale", ("popoli",)),
]

UNIDENTIFIED_PREFIX = "JOURNAL NON IDENTIFIÉ"
UNKNOWN_RANK = 1000
UNIDENTIFIED_RANK = 2000
# Un nom lu sur une photo peut avoir une lettre fausse : au-delà de ce taux de ressemblance
# (et pour un nom assez long pour que ce soit significatif), c'est le même journal.
FUZZY_RATIO = 0.88
FUZZY_MIN_LENGTH = 8


def plain(text):
    """Forme de comparaison : minuscules ASCII, ponctuation -> espace (« L'Œil » -> « l oeil »)."""
    text = str(text or "").replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


@lru_cache(maxsize=1)
def _index():
    exact = {}
    for rank, (name, rubrique, aliases) in enumerate(KNOWN_MEDIA):
        media = {"name": name, "rubrique": rubrique, "rank": rank}
        for alias in (name, *aliases):
            exact.setdefault(plain(alias), media)
    return exact


def identify(source):
    """Journal connu correspondant à `source`, avec `exact` = False quand seul le début du nom
    correspond (« MUTATIONS (30 ANS) ») : le nom affiché est alors conservé tel quel."""
    key = plain(source)
    if not key:
        return None
    exact = _index()
    if key in exact:
        return {**exact[key], "exact": True}
    if len(key) >= FUZZY_MIN_LENGTH:
        best, ratio = None, 0.0
        for alias, media in exact.items():
            r = SequenceMatcher(None, key, alias).ratio()
            if r > ratio:
                best, ratio = media, r
        if ratio >= FUZZY_RATIO:
            return {**best, "exact": True}
    for alias, media in sorted(exact.items(), key=lambda item: -len(item[0])):
        if len(alias) >= 6 and key.startswith(alias + " "):
            return {**media, "exact": False}
    return None


def display_name(source):
    """Nom à afficher : la graphie de référence d'un journal reconnu, sinon le nom tel quel."""
    media = identify(source)
    return media["name"] if media and media["exact"] else (source or "").strip()


def forced_rubrique(source):
    media = identify(source)
    return media["rubrique"] if media else None


def rank(source):
    """Clé de tri : grands titres d'abord, puis inconnus, puis journal non identifié."""
    if (source or "").strip().upper().startswith(UNIDENTIFIED_PREFIX):
        return UNIDENTIFIED_RANK
    media = identify(source)
    return media["rank"] if media else UNKNOWN_RANK
