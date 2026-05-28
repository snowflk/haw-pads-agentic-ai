from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from shared.schemas import KnowledgeChunk

load_dotenv(override=True)

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS_DIR = APP_DIR / "data" / "corpus"
DEFAULT_DB_DIR = APP_DIR / "chroma_db"
COLLECTION_NAME = "template_agent_knowledge"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class TemplateVectorStore:
    def __init__(self, db_dir: Path = DEFAULT_DB_DIR):
        self.client = chromadb.PersistentClient(path=str(db_dir))
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        self.openai_client = OpenAI()

    def seed_from_markdown(self, corpus_dir: Path = DEFAULT_CORPUS_DIR) -> int:
        documents = list(_load_markdown_documents(corpus_dir))
        if not documents:
            return 0

        chunks = []
        for source, text in documents:
            chunks.extend(_chunk_text(source=source, text=text))

        if not chunks:
            return 0

        ids = [_chunk_id(chunk.source, idx) for idx, chunk in enumerate(chunks)]
        embeddings = self._embed([chunk.text for chunk in chunks])
        metadatas: list[dict[str, str]] = [{"source": chunk.source, **chunk.metadata} for chunk in chunks]

        self.collection.upsert(
            ids=ids,
            documents=[chunk.text for chunk in chunks],
            embeddings=cast(Any, embeddings),
            metadatas=cast(Any, metadatas),
        )
        return len(chunks)

    def query(self, question: str, top_k: int = 3) -> list[KnowledgeChunk]:
        embedding = self._embed([question])[0]
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=max(1, min(top_k, 8)),
            include=["documents", "metadatas", "distances"],
        )

        documents_result = cast(list[list[str]], result.get("documents") or [[]])
        metadatas_result = cast(list[list[dict[str, object] | None]], result.get("metadatas") or [[]])
        distances_result = cast(list[list[float | None]], result.get("distances") or [[]])
        documents = documents_result[0] if documents_result else []
        metadatas = metadatas_result[0] if metadatas_result else []
        distances = distances_result[0] if distances_result else []

        chunks: list[KnowledgeChunk] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            metadata = metadata or {}
            chunks.append(
                KnowledgeChunk(
                    text=text,
                    source=str(metadata.get("source", "unknown")),
                    score=float(distance) if distance is not None else None,
                    metadata={str(k): str(v) for k, v in metadata.items() if k != "source"},
                )
            )
        return chunks

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self.openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            print(f"OpenAI embeddings failed, using deterministic fallback embeddings: {exc}")
            return [_hash_embedding(text) for text in texts]


def _load_markdown_documents(corpus_dir: Path) -> list[tuple[str, str]]:
    if not corpus_dir.exists():
        return []
    documents = []
    for path in sorted(corpus_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append((path.name, text))
    return documents


def _chunk_text(source: str, text: str, max_chars: int = 1200, overlap: int = 150) -> list[KnowledgeChunk]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(KnowledgeChunk(text=chunk_text, source=source))
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _chunk_id(source: str, idx: int) -> str:
    digest = hashlib.sha1(f"{source}:{idx}".encode("utf-8")).hexdigest()
    return digest


def _hash_embedding(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for idx in range(EMBEDDING_DIMENSIONS):
        byte = digest[idx % len(digest)]
        values.append((byte / 255.0) - 0.5)
    return values
