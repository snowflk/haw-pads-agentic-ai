from __future__ import annotations

from typing import Any

from knowledge.vector_store import LibraryVectorStore


def lookup_library_info(vector_store: LibraryVectorStore, question: str, top_k: int = 3) -> dict[str, Any]:
    """Retrieve library information from the crawled HIBS knowledge base."""
    chunks = vector_store.query(question=question, top_k=top_k)
    return {"chunks": chunks, "count": len(chunks)}
