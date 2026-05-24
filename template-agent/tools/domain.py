from __future__ import annotations

from shared.schemas import DomainRecord


# TODO: Replace this sample data with an API call, database lookup, CSV query,
# web request, or any other concrete data source for the exercise.
SAMPLE_RECORDS = [
    DomainRecord(
        id="demo-1",
        title="Example onboarding guide",
        description="A sample record showing how structured tool results flow back to the agent.",
        source="tools/domain.py",
    ),
    DomainRecord(
        id="demo-2",
        title="Example troubleshooting note",
        description="A second record students can replace with their own application data.",
        source="tools/domain.py",
    ),
]


def search_domain_records(query: str, limit: int = 5) -> list[DomainRecord]:
    """Search structured domain records.

    This intentionally starts simple. Students should replace the matching logic
    with real application behavior while keeping the function interface stable.
    """
    query_tokens = {token.lower() for token in query.split() if token.strip()}
    scored: list[tuple[int, DomainRecord]] = []

    for record in SAMPLE_RECORDS:
        haystack = f"{record.title} {record.description}".lower()
        score = sum(1 for token in query_tokens if token in haystack)
        if score > 0 or not query_tokens:
            scored.append((score, record))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in scored[: max(1, min(limit, 20))]]


def serialize_domain_records(records: list[DomainRecord]) -> list[dict[str, str | None]]:
    return [record.model_dump() for record in records]
