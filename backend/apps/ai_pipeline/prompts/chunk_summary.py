from .source_text import SOURCE_GUARD, wrap_source


def build_chunk_summary_prompt(chunk_text):
    system_prompt = (
        "Tu es un assistant qui résume des extraits d'articles de presse camerounais "
        "en français, de façon neutre et factuelle, pour préparer une revue de presse "
        "professionnelle. Réponds uniquement en JSON valide. La valeur de \"summary\" doit être "
        "UNE SEULE chaîne de texte continu (3 à 5 phrases) — jamais une liste, jamais un objet. "
        'Exemple de format : {"summary": "Le gouvernement annonce un projet de loi. Le ministre précise ..."}\n\n'
        f"{SOURCE_GUARD}"
    )
    user_prompt = f"Résume cet extrait en 3 à 5 phrases, en conservant les faits clés :\n\n{wrap_source(chunk_text)}"
    return system_prompt, user_prompt
