from __future__ import annotations

from pydantic import BaseModel, Field


class DomainRecord(BaseModel):
    id: str
    title: str
    description: str
    source: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    text: str
    source: str
    score: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
