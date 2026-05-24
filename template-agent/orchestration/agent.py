from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agents import Agent as SdkAgent
from agents import Runner, function_tool
from pydantic import BaseModel, Field, ValidationError

from knowledge.vector_store import TemplateVectorStore
from model.llm import SYSTEM_PROMPT
from shared.schemas import DomainRecord
from tools.domain import search_domain_records, serialize_domain_records
from tools.knowledge import lookup_knowledge


class SearchDomainArgs(BaseModel):
    query: str = Field(min_length=1, description="The search query for structured domain records.")
    limit: int = Field(default=5, ge=1, le=20)


class LookupKnowledgeArgs(BaseModel):
    question: str = Field(min_length=1, description="The user's question for the local knowledge base.")
    top_k: int = Field(default=3, ge=1, le=8)


@dataclass
class AgentTrace:
    tool_name: str
    arguments: dict[str, Any]
    output: Any


@dataclass
class AgentResult:
    answer: str
    records: list[DomainRecord] = field(default_factory=list)
    traces: list[AgentTrace] = field(default_factory=list)


class TemplateAgent:
    """Orchestration layer.

    This class wires model, prompt, tools, memory, validation, traces, and final output.
    The OpenAI Agents SDK Runner executes the actual model/tool loop.
    """

    def __init__(self, model: str, vector_store: TemplateVectorStore):
        self.model = model
        self.vector_store = vector_store
        self._latest_records: list[DomainRecord] = []
        self._runtime_traces: list[AgentTrace] = []
        self._max_results = 5
        self._agent = self._build_agent()

    def run(self, messages: list[dict[str, str]], max_results: int = 5) -> AgentResult:
        self._latest_records = []
        self._runtime_traces = []
        self._max_results = max(1, min(max_results, 20))

        run_result = Runner.run_sync(self._agent, messages)
        final_output = run_result.final_output
        answer = final_output if isinstance(final_output, str) else json.dumps(final_output, indent=2)

        return AgentResult(
            answer=answer,
            records=self._latest_records,
            traces=list(self._runtime_traces),
        )

    def _build_agent(self) -> SdkAgent:
        @function_tool
        def search_domain_tool(query: str, limit: int = 5) -> dict[str, Any]:
            """Search the app's structured domain data.

            TODO: Students can rename this tool and adapt its parameters once
            they know their application domain.
            """
            try:
                args = SearchDomainArgs.model_validate({"query": query, "limit": limit})
            except ValidationError as exc:
                payload = {"error": "Invalid arguments for search_domain_tool", "details": exc.errors()}
                self._runtime_traces.append(
                    AgentTrace(
                        tool_name="search_domain_tool",
                        arguments={"query": query, "limit": limit},
                        output=payload,
                    )
                )
                return payload

            safe_limit = min(args.limit, self._max_results)
            records = search_domain_records(query=args.query, limit=safe_limit)
            self._latest_records = records
            payload = {"records": serialize_domain_records(records), "count": len(records)}
            self._runtime_traces.append(
                AgentTrace(
                    tool_name="search_domain_tool",
                    arguments={"query": args.query, "limit": safe_limit},
                    output=payload,
                )
            )
            return payload

        @function_tool
        def lookup_knowledge_tool(question: str, top_k: int = 3) -> dict[str, Any]:
            """Search the local Chroma knowledge base built from markdown files."""
            try:
                args = LookupKnowledgeArgs.model_validate({"question": question, "top_k": top_k})
            except ValidationError as exc:
                payload = {"error": "Invalid arguments for lookup_knowledge_tool", "details": exc.errors()}
                self._runtime_traces.append(
                    AgentTrace(
                        tool_name="lookup_knowledge_tool",
                        arguments={"question": question, "top_k": top_k},
                        output=payload,
                    )
                )
                return payload

            payload = lookup_knowledge(self.vector_store, question=args.question, top_k=args.top_k)
            self._runtime_traces.append(
                AgentTrace(
                    tool_name="lookup_knowledge_tool",
                    arguments={"question": args.question, "top_k": args.top_k},
                    output=payload,
                )
            )
            return payload

        return SdkAgent(
            name="Template Agent",
            model=self.model,
            instructions=SYSTEM_PROMPT,
            tools=[search_domain_tool, lookup_knowledge_tool],
        )
