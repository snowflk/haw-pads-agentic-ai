from __future__ import annotations

from dotenv import load_dotenv

from knowledge.vector_store import TemplateVectorStore


def main() -> None:
    load_dotenv(override=True)
    vector_store = TemplateVectorStore()
    count = vector_store.seed_from_markdown()
    print(f"Seeded {count} knowledge chunks into ChromaDB.")


if __name__ == "__main__":
    main()
