from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from knowledge.vector_store import LibraryVectorStore


def main() -> None:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(description="Seed ChromaDB with crawled HIBS markdown files.")
    parser.add_argument("--corpus-dir", default="data/corpus", help="Path to crawled markdown corpus.")
    parser.add_argument("--no-reset", action="store_true", help="Do not reset collection before seeding.")
    args = parser.parse_args()

    store = LibraryVectorStore()
    seeded = store.seed_from_markdown_dir(Path(args.corpus_dir), reset=not args.no_reset)
    print(f"Seeded {seeded} chunks into Chroma collection.")
    print(f"Collection count: {store.count()}")


if __name__ == "__main__":
    main()
