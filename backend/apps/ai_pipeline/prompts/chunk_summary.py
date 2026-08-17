def build_chunk_summary_prompt(chunk_text):
    system_prompt = (
        "Tu es un assistant qui résume des extraits d'articles de presse camerounais "
        "en français, de façon neutre et factuelle, pour préparer une revue de presse "
        'professionnelle. Réponds uniquement en JSON valide de la forme {"summary": "..."}.'
    )
    user_prompt = f"Résume cet extrait en 3 à 5 phrases, en conservant les faits clés :\n\n{chunk_text}"
    return system_prompt, user_prompt
