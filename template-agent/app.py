from __future__ import annotations

from typing import Literal, cast

import streamlit as st
from agents.items import TResponseInputItem
from dotenv import load_dotenv
from openai.types.responses.easy_input_message_param import EasyInputMessageParam

from knowledge.vector_store import TemplateVectorStore
from model.llm import DEFAULT_MODEL
from orchestration.agent import TemplateAgent
from shared.schemas import DomainRecord

load_dotenv(override=True)

AgentMessageRole = Literal["user", "assistant"]


@st.cache_resource
def get_vector_store() -> TemplateVectorStore:
    return TemplateVectorStore()


def render_records(records: list[DomainRecord]) -> None:
    if not records:
        return
    st.subheader("Structured Tool Results")
    st.dataframe([record.model_dump() for record in records], use_container_width=True, hide_index=True)


def build_agent_messages(chat_messages: list[dict[str, object]]) -> list[TResponseInputItem]:
    """Convert Streamlit chat state into agent input messages."""
    output: list[TResponseInputItem] = []
    for msg in chat_messages:
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            output.append(EasyInputMessageParam(role=cast(AgentMessageRole, role), content=content))
    return output


def main() -> None:
    st.set_page_config(page_title="Template Agent", page_icon="A", layout="wide")
    st.title("Template Agent")
    st.caption("A small scaffold for teaching model, tools, orchestration, and RAG.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.header("Agent Settings")
        model = st.text_input("Model", value=DEFAULT_MODEL)
        max_results = st.slider("Max structured results", min_value=1, max_value=20, value=5)
        show_tool_traces = st.toggle("Show tool traces", value=True)

        if st.button("New conversation"):
            st.session_state.messages = []
            st.rerun()

        st.markdown("---")
        st.markdown("Teaching Map")
        st.code("model/llm.py\norchestration/agent.py\ntools/\nknowledge/", language="text")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("records"):
                render_records(msg["records"])
            if msg["role"] == "assistant" and show_tool_traces and msg.get("traces"):
                with st.expander("Tool traces"):
                    for idx, trace in enumerate(msg["traces"], start=1):
                        st.write(f"Tool {idx}: `{trace['tool_name']}`")
                        st.json({"arguments": trace["arguments"], "output": trace["output"]})

    user_prompt = st.chat_input("Ask a question about your domain or knowledge base.")
    if not user_prompt:
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        try:
            agent = TemplateAgent(model=model, vector_store=get_vector_store())
            result = agent.run(build_agent_messages(st.session_state.messages), max_results=max_results)
            st.markdown(result.answer)
            render_records(result.records)
            if show_tool_traces and result.traces:
                with st.expander("Tool traces"):
                    for idx, trace in enumerate(result.traces, start=1):
                        st.write(f"Tool {idx}: `{trace.tool_name}`")
                        st.json({"arguments": trace.arguments, "output": trace.output})
        except Exception as exc:
            result = None
            st.error(f"Agent error: {exc}")

    if result:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": result.answer,
                "records": result.records,
                "traces": [
                    {"tool_name": trace.tool_name, "arguments": trace.arguments, "output": trace.output}
                    for trace in result.traces
                ],
            }
        )
    else:
        st.session_state.messages.append({"role": "assistant", "content": "Failed to generate response."})


if __name__ == "__main__":
    main()
