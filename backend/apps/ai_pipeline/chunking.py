"""Découpage des documents longs en chunks exploitables par Mistral. Aligné sur les
sauts de page (\\f, insérés par extraction.py) pour pouvoir rattacher chaque highlight
détecté à un numéro de page approximatif."""
from dataclasses import dataclass
from typing import Optional

CHARS_PER_TOKEN_ESTIMATE = 4
TARGET_TOKENS_PER_CHUNK = 6000
TARGET_CHARS_PER_CHUNK = TARGET_TOKENS_PER_CHUNK * CHARS_PER_TOKEN_ESTIMATE


@dataclass
class TextChunk:
    text: str
    page_start: Optional[int]
    page_end: Optional[int]


def chunk_document_text(text, target_chars=TARGET_CHARS_PER_CHUNK):
    if not text or not text.strip():
        return []

    pages = text.split("\f")
    chunks = []
    current_pages = []
    current_len = 0
    start_page = 1

    for idx, page_text in enumerate(pages, start=1):
        current_pages.append(page_text)
        current_len += len(page_text)
        is_last_page = idx == len(pages)
        if current_len >= target_chars or is_last_page:
            chunk_text = "\f".join(current_pages).strip()
            if chunk_text:
                chunks.append(TextChunk(text=chunk_text, page_start=start_page, page_end=idx))
            current_pages = []
            current_len = 0
            start_page = idx + 1

    return chunks
