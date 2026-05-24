from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agents import Agent as SdkAgent
from agents import Runner, function_tool
from knowledge.vector_store import LibraryVectorStore
from model.llm import SYSTEM_PROMPT
from pydantic import BaseModel, Field, ValidationError
from shared.schemas import BookRecord
from tools.catalog import search_haw_books_advanced, serialize_books_for_tool
from tools.library_info import lookup_library_info


class SearchBooksArgs(BaseModel):
    query: str | None = Field(default=None, description="Optional free-text query.")
    title: str | None = Field(default=None, description="Expected title or topic.")
    author: str | None = Field(default=None, description="Expected author name.")
    limit: int = Field(default=5, ge=1, le=20)


class RetrieveLibraryInfoArgs(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=8)


@dataclass
class AgentTrace:
    tool_name: str
    arguments: dict[str, Any]
    output: Any


@dataclass
class AgentResult:
    answer: str
    books: list[BookRecord] = field(default_factory=list)
    traces: list[AgentTrace] = field(default_factory=list)


class LibraryAgent:
    def __init__(self, model: str, vector_store: LibraryVectorStore):
        self.model = model
        self.vector_store = vector_store
        self._latest_books: list[BookRecord] = []
        self._runtime_traces: list[AgentTrace] = []
        self._max_book_results = 5
        self._agent = self._build_agent()

    def run(
        self, messages: list[dict[str, str]], max_book_results: int = 5
    ) -> AgentResult:
        self._latest_books = []
        self._runtime_traces = []
        self._max_book_results = max(1, min(max_book_results, 20))

        run_result = Runner.run_sync(self._agent, messages)
        final_output = run_result.final_output
        if isinstance(final_output, str):
            answer = final_output
        else:
            answer = json.dumps(final_output, ensure_ascii=False, indent=2)

        return AgentResult(
            answer=answer, books=self._latest_books, traces=list(self._runtime_traces)
        )

    def _build_agent(self) -> SdkAgent:
        @function_tool
        def search_haw_books_tool(
            query: str | None = None,
            title: str | None = None,
            author: str | None = None,
            limit: int = 5,
        ) -> dict[str, Any]:
            """Search HAW Hamburg catalog and return books with availability and location.
            Prefer passing title and author explicitly when known.
            """
            try:
                args = SearchBooksArgs.model_validate(
                    {"query": query, "title": title, "author": author, "limit": limit}
                )
            except ValidationError as exc:
                payload = {
                    "error": "Invalid arguments for search_haw_books_tool",
                    "details": exc.errors(),
                }
                self._runtime_traces.append(
                    AgentTrace(
                        tool_name="search_haw_books_tool",
                        arguments={
                            "query": query,
                            "title": title,
                            "author": author,
                            "limit": limit,
                        },
                        output=payload,
                    )
                )
                return payload

            if not any([args.query, args.title, args.author]):
                payload = {
                    "error": "At least one of query/title/author must be provided."
                }
                self._runtime_traces.append(
                    AgentTrace(
                        tool_name="search_haw_books_tool",
                        arguments={
                            "query": query,
                            "title": title,
                            "author": author,
                            "limit": limit,
                        },
                        output=payload,
                    )
                )
                return payload

            safe_limit = min(args.limit, self._max_book_results)
            books = search_haw_books_advanced(
                query=args.query,
                title=args.title,
                author=args.author,
                limit=safe_limit,
                enrich_availability=True,
            )
            self._latest_books = books
            payload = {"books": serialize_books_for_tool(books), "count": len(books)}
            self._runtime_traces.append(
                AgentTrace(
                    tool_name="search_haw_books_tool",
                    arguments={
                        "query": args.query,
                        "title": args.title,
                        "author": args.author,
                        "limit": safe_limit,
                    },
                    output=payload,
                )
            )
            return payload

        @function_tool
        def lookup_library_info_tool(question: str, top_k: int = 3) -> dict[str, Any]:
            """Retrieve library information from crawled HIBS pages (opening hours, contacts, addresses)."""
            try:
                args = RetrieveLibraryInfoArgs.model_validate(
                    {"question": question, "top_k": top_k}
                )
            except ValidationError as exc:
                payload = {
                    "error": "Invalid arguments for lookup_library_info_tool",
                    "details": exc.errors(),
                }
                self._runtime_traces.append(
                    AgentTrace(
                        tool_name="lookup_library_info_tool",
                        arguments={"question": question, "top_k": top_k},
                        output=payload,
                    )
                )
                return payload

            payload = lookup_library_info(
                self.vector_store, question=args.question, top_k=args.top_k
            )
            self._runtime_traces.append(
                AgentTrace(
                    tool_name="lookup_library_info_tool",
                    arguments={"question": args.question, "top_k": args.top_k},
                    output=payload,
                )
            )
            return payload

        return SdkAgent(
            name="HAW Library Agent",
            model=self.model,
            instructions=SYSTEM_PROMPT,
            tools=[search_haw_books_tool, lookup_library_info_tool],
        )
