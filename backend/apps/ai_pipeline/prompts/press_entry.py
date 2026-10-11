from ..press_format import RUBRIQUES
from .source_text import SOURCE_GUARD, safe_filename, wrap_source

# Au-delà, le début du texte suffit à identifier le journal et sa une ; la suite est
# couverte par les résumés des extraits (étape précédente).
MAX_TEXT_CHARS = 6000


def build_press_entry_prompt(*, filename, text, chunk_summaries):
    rubriques = "\n".join(f'- "{r["key"]}" : {r["hint"]}' for r in RUBRIQUES)
    system_prompt = (
        "Tu es documentaliste dans la cellule de communication d'une entreprise au Cameroun. "
        "Chaque matin tu rédiges la revue de presse : pour chaque journal, une notice courte et "
        "factuelle. On te donne le texte lu sur une page de journal (souvent la une) et, pour "
        "les longs documents, des résumés de leurs articles.\n\n"
        "Réponds UNIQUEMENT en JSON valide de la forme :\n"
        '{"journal": "...", "rubrique": "...", "titre": "...", "resume": "..."}\n\n'
        "- journal : nom du journal en MAJUSCULES tel qu'il figure dans le titre / l'en-tête "
        '(ex : "CAMEROON TRIBUNE", "LE JOUR", "MUTATIONS"). Chaîne vide si introuvable.\n'
        f"- rubrique : le TYPE de journal, parmi les clés suivantes :\n{rubriques}\n"
        "  Les quotidiens et hebdomadaires d'information générale (Cameroon Tribune, Le Jour, "
        "Mutations, Le Messager, La Nouvelle Expression, Emergence, The Guardian Post, The Sun, "
        'etc.) vont TOUJOURS dans "generale", quel que soit le sujet de leur une. Les autres '
        "clés sont réservées aux journaux spécialisés (économiques, régionaux, santé, sport…) ; "
        '"deces" seulement si la page est entièrement consacrée à un décès ou un hommage.\n'
        "- titre : le titre principal de la une, recopié mot pour mot, sans guillemets. Chaîne "
        "vide s'il n'y en a pas.\n"
        "- resume : texte brut en français (sans Markdown, sans gras, sans liste), au présent, "
        "dans le style d'une revue de presse : d'abord le sujet principal (« Le quotidien ouvre "
        "sur… », « Le journal révèle… »), puis les autres sujets de la page (« En marge, … », "
        "« Le journal évoque aussi… »). De 1 à 5 phrases selon la quantité d'informations : une "
        "page avec un seul article tient en 1 à 3 phrases. Garde les chiffres, noms, fonctions "
        "et dates exacts. N'invente rien, ne commente pas, ne conclus pas, ne signale pas ce qui "
        "manque et ne répète pas le titre.\n\n"
        f"{SOURCE_GUARD}"
    )
    text = text or ""
    user_prompt = f"Fichier : {safe_filename(filename)}\n\nTexte lu sur la page :\n{wrap_source(text[:MAX_TEXT_CHARS])}"
    # Les résumés ne servent qu'à couvrir la fin d'un long document (PDF de plusieurs pages) :
    # pour une photo de une, le texte complet suffit, et des résumés déjà reformulés
    # n'apportent que des risques de paraphrase inexacte. Ils dérivent du texte source : même
    # bloc délimité, même statut de simple donnée.
    if len(text) > MAX_TEXT_CHARS:
        summaries_block = "\n".join(f"- {s}" for s in chunk_summaries if s) or "(aucun)"
        user_prompt += f"\n\nRésumés de l'ensemble des articles du document :\n{wrap_source(summaries_block)}"
    return system_prompt, user_prompt
