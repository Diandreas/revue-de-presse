"""Schémas pydantic validant les réponses JSON de Mistral avant toute écriture en base."""
from typing import Optional

from pydantic import BaseModel, Field


class ChunkSummaryResult(BaseModel):
    summary: str


class HighlightItem(BaseModel):
    category_name: str
    excerpt: str
    explanation: str = ""
    confidence: Optional[float] = None


class HighlightDetectionResult(BaseModel):
    highlights: list[HighlightItem] = Field(default_factory=list)


class ReviewDraftResult(BaseModel):
    summary_markdown: str
