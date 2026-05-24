from __future__ import annotations

from pydantic import BaseModel, Field


class DomainRecord(BaseModel):
    """Example structured result returned by a domain tool.

    TODO: Replace this with fields from the students' application domain.
    Examples: Product, Event, Course, Ticket, Recipe, PatientIntake, etc.
    """

    id: str
    title: str
    description: str
    source: str | None = None


class KnowledgeChunk(BaseModel):
    text: str
    source: str
    score: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
