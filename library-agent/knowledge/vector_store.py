from __future__ import annotations

import hashlib
import math
import os
import sys
from pathlib import Path
from typing import Any, cast

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

CHROMA_DIR = Path("chroma_db")
COLLECTION_NAME = "haw_hibs_library_pages"
EMBED_MODEL = "text-embedding-3-small"


class LibraryVectorStore:
    def __init__(self, chroma_dir: Path = CHROMA_DIR, collection_name: str = COLLECTION_NAME):
        load_dotenv(override=True)
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        self._openai = OpenAI() if os.getenv("OPENAI_API_KEY") else None

    def seed_from_markdown_dir(self, corpus_dir: Path, reset: bool = True, chunk_size: int = 1200) -> int:
        corpus_dir = corpus_dir.resolve()
        files = sorted(corpus_dir.glob("*.md"))
        if not files:
            raise RuntimeError(f"No markdown files found in {corpus_dir}")

        if reset:
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )

        chunks: list[str] = []
        metadatas: list[dict[str, str | int]] = []
        ids: list[str] = []
        for file in files:
            text = file.read_text(encoding="utf-8")
            for idx, chunk in enumerate(chunk_markdown(text, chunk_size=chunk_size)):
                chunk = chunk.strip()
                if not chunk:
                    continue
                doc_id = stable_id(file.name, idx, chunk)
                ids.append(doc_id)
                chunks.append(chunk)
                metadatas.append({"source_file": file.name, "chunk_index": idx})

        if not chunks:
            raise RuntimeError("No chunks produced from corpus.")

        embeddings = embed_texts(chunks, model=EMBED_MODEL, client=self._openai)
        self.collection.add(
            ids=ids,
            documents=chunks,
            metadatas=cast(Any, metadatas),
            embeddings=cast(Any, embeddings),
        )
        return len(chunks)

    def query(self, question: str, top_k: int = 3) -> list[dict[str, Any]]:
        question_embedding = embed_texts([question], model=EMBED_MODEL, client=self._openai)[0]
        result = self.collection.query(
            query_embeddings=[question_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        rows: list[dict[str, Any]] = []
        for i, doc in enumerate(docs):
            rows.append(
                {
                    "content": doc,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distances[i] if i < len(distances) else None,
                }
            )
        return rows

    def count(self) -> int:
        return self.collection.count()


def embed_texts(texts: list[str], model: str, client: OpenAI | None = None) -> list[list[float]]:
    if client is None:
        return [hash_embedding(text) for text in texts]

    out: list[list[float]] = []
    batch_size = 64
    try:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(model=model, input=batch)
            out.extend([item.embedding for item in response.data])
        return out
    except Exception:
        print(
            "Warning: OpenAI embeddings failed; falling back to local hash embeddings.",
            file=sys.stderr,
        )
        return [hash_embedding(text) for text in texts]


def chunk_markdown(text: str, chunk_size: int = 1200) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines()]
    sections: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        if not line:
            continue
        extra = len(line) + 1
        if current and (current_len + extra > chunk_size or line.startswith("#")):
            sections.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += extra

    if current:
        sections.append("\n".join(current))
    return sections


def stable_id(filename: str, idx: int, chunk: str) -> str:
    digest = hashlib.sha1(chunk.encode("utf-8")).hexdigest()[:12]
    return f"{filename}:{idx}:{digest}"


def hash_embedding(text: str, dim: int = 384) -> list[float]:
    vec = [0.0] * dim
    for token in text.lower().split():
        bucket = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim
        vec[bucket] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
