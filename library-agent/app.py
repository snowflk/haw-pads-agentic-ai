from __future__ import annotations
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from knowledge.vector_store import LibraryVectorStore
from model.llm import DEFAULT_MODEL
from orchestration.agent import LibraryAgent
from shared.schemas import BookRecord

load_dotenv(override=True)

APP_DIR = Path(__file__).resolve().parent
CORPUS_PATH = APP_DIR / "data" / "corpus"


@st.cache_resource
def get_vector_store() -> LibraryVectorStore:
    return LibraryVectorStore()


def render_books(books: list[BookRecord]) -> None:
    if not books:
        return

    st.subheader("Book Results")
    rows = []
    for b in books:
        rows.append(
            {
                "Title": b.display_title,
                "Author(s)": ", ".join(b.authors) if b.authors else (b.responsibility or ""),
                "Year": b.year or "",
                "Location": b.availability.location if b.availability and b.availability.location else "",
                "Shelfmark": b.availability.shelfmark
                if b.availability and b.availability.shelfmark
                else (b.local_shelfmark or ""),
                "Availability": b.availability.loan_status if b.availability else "",
                "Loan Type": b.availability.loan_indication if b.availability else "",
                "PPN": b.ppn,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def build_agent_messages(chat_messages: list[dict[str, object]]) -> list[dict[str, str]]:
    """Convert Streamlit chat state into OpenAI Agents input messages."""
    output: list[dict[str, str]] = []
    for msg in chat_messages:
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            output.append({"role": role, "content": content})
    return output


def main() -> None:
    st.set_page_config(page_title="HAW Library Agent", page_icon="📚", layout="wide")
    st.title("HAW Library Agent")
    st.caption("Tool-calling agent with HAW catalog search and HIBS vector RAG.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.header("Settings")
        model = st.text_input("Model", value=DEFAULT_MODEL)
        max_results = st.slider("Max catalog results", min_value=1, max_value=20, value=5)
        show_tool_traces = st.toggle("Show tool traces", value=True)
        if st.button("New conversation"):
            st.session_state.messages = []
            st.rerun()
        st.markdown("---")
        st.markdown("Corpus + Vector DB")
        st.code(str(CORPUS_PATH), language="text")
        st.code(str(APP_DIR / "chroma_db"), language="text")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("books"):
                render_books(msg["books"])
            if msg["role"] == "assistant" and show_tool_traces and msg.get("traces"):
                with st.expander("Tool traces"):
                    for idx, trace in enumerate(msg["traces"], start=1):
                        st.write(f"Tool {idx}: `{trace['tool_name']}`")
                        st.json({"arguments": trace["arguments"], "output": trace["output"]})

    user_prompt = st.chat_input("Ask for books, availability, locations, opening hours, or contacts.")
    if not user_prompt:
        return

    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        try:
            agent = LibraryAgent(model=model, vector_store=get_vector_store())
            result = agent.run(build_agent_messages(st.session_state.messages), max_book_results=max_results)
            st.markdown(result.answer)
            render_books(result.books)
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
                "books": result.books,
                "traces": [
                    {"tool_name": t.tool_name, "arguments": t.arguments, "output": t.output}
                    for t in result.traces
                ],
            }
        )
    else:
        st.session_state.messages.append({"role": "assistant", "content": "Failed to generate response."})


if __name__ == "__main__":
    main()
