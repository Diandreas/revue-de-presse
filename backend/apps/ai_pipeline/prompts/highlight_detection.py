def _format_categories(categories):
    lines = []
    for category in categories:
        keywords = ", ".join(category.keywords) if category.keywords else "aucun"
        lines.append(
            f"- {category.name} (type: {category.type}) : {category.description}\n"
            f"  Instruction de détection : {category.prompt_hint}\n"
            f"  Mots-clés indicatifs : {keywords}"
        )
    return "\n".join(lines)


def build_highlight_detection_prompt(chunk_text, categories):
    """`categories` : liste de DetectionCategory actives (org-scopées + globales).
    C'est l'unique point d'entrée du contenu "critères légaux/intox" dans les prompts —
    aucun texte de loi n'est codé en dur ici, tout vient de la base éditable via l'admin."""
    categories_block = _format_categories(categories)
    system_prompt = (
        "Tu es un analyste qui prépare une revue de presse professionnelle pour une "
        "entreprise au Cameroun. Tu identifies dans un extrait d'article les passages "
        "pertinents selon les catégories fournies ci-dessous. Ne signale que ce qui "
        "correspond clairement à une catégorie — pas de sur-interprétation. Réponds "
        'uniquement en JSON valide de la forme {"highlights": [{"category_name": "...", '
        '"excerpt": "...", "explanation": "...", "confidence": 0.0}]}. Utilise exactement '
        "le nom de catégorie fourni dans category_name. Renvoie une liste vide si rien "
        "n'est pertinent.\n\n"
        f"Catégories disponibles :\n{categories_block}"
    )
    user_prompt = f"Extrait à analyser :\n\n{chunk_text}"
    return system_prompt, user_prompt
