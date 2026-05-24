from __future__ import annotations

from typing import Any

from knowledge.vector_store import TemplateVectorStore


def lookup_knowledge(vector_store: TemplateVectorStore, question: str, top_k: int = 3) -> dict[str, Any]:
    """Retrieve relevant chunks from the local Chroma knowledge base."""
    chunks = vector_store.query(question=question, top_k=top_k)
    return {"chunks": [chunk.model_dump() for chunk in chunks], "count": len(chunks)}
