def build_review_drafting_prompt(*, document_titles, chunk_summaries, highlights):
    summaries_block = "\n".join(f"- {s}" for s in chunk_summaries) or "Aucun résumé disponible."
    highlights_block = (
        "\n".join(
            f"- [{h['category_name']}] {h['excerpt']} — {h.get('explanation', '')}" for h in highlights
        )
        or "Aucun point saillant détecté."
    )
    titles_block = ", ".join(document_titles) or "document(s) non titré(s)"

    system_prompt = (
        "Tu es rédacteur d'une revue de presse professionnelle pour une entreprise au "
        "Cameroun. À partir des résumés et des points saillants fournis, rédige une "
        "revue de presse structurée et concise en français, en Markdown (titres, "
        "sections, listes à puces). Structure attendue : un titre, une section "
        "'Résumé exécutif', une section par catégorie de point saillant détecté, une "
        'conclusion. Réponds uniquement en JSON valide de la forme {"summary_markdown": "..."}.'
    )
    user_prompt = (
        f"Documents source : {titles_block}\n\n"
        f"Résumés des extraits :\n{summaries_block}\n\n"
        f"Points saillants détectés :\n{highlights_block}"
    )
    return system_prompt, user_prompt
