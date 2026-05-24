from __future__ import annotations

from pydantic import BaseModel, Field


class AvailabilityInfo(BaseModel):
    location: str | None = None
    shelfmark: str | None = None
    loan_indication: str | None = None
    loan_status: str | None = None
    description: str | None = None
    action_description: str | None = None
    action_url: str | None = None


class BookRecord(BaseModel):
    ppn: str
    title: str
    subtitle: str | None = None
    responsibility: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: str | None = None
    isbn: list[str] = Field(default_factory=list)
    epn: str | None = None
    library_sigel: str | None = None
    local_shelfmark: str | None = None
    media_number: str | None = None
    availability: AvailabilityInfo | None = None

    @property
    def display_title(self) -> str:
        if self.subtitle:
            return f"{self.title}: {self.subtitle}"
        return self.title
