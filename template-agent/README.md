# Template Agent

This is a teaching skeleton for an agentic AI exercise. It is intentionally small, but runnable.

Students should focus on three things:

1. Build useful tools.
2. Write a clear system prompt.
3. Wire the tools into the orchestration layer.

## Architecture

```text
template-agent/
  app.py                    # Streamlit UI
  model/
    llm.py                  # Model choice and system prompt
  orchestration/
    agent.py                # Orchestration layer
  tools/
    domain.py               # Structured domain tool placeholder
    knowledge.py            # RAG lookup tool wrapper
  knowledge/
    vector_store.py         # ChromaDB + embeddings
  shared/
    schemas.py              # Pydantic data models
  data/corpus/
    getting-started.md      # Starter markdown for RAG
  seed_chroma.py            # Seeds local markdown into ChromaDB
  Makefile
```

## Concepts

### Model

Edit `model/llm.py`.

Students should change:

- `DEFAULT_MODEL`
- `SYSTEM_PROMPT`
- Tool usage rules
- Answer style
- Failure behavior

### Tools

Edit `tools/domain.py` and optionally `tools/knowledge.py`.

Students should replace the sample tool with something concrete, for example:

- Search a CSV file.
- Call a public API.
- Query a local JSON file.
- Validate user input.
- Calculate or transform domain data.

### Orchestration Layer

Edit `orchestration/agent.py`.

This is where the app wires together:

- Model
- System prompt
- Tools
- Tool argument validation
- Tool traces
- Explicit message history from Streamlit state (app-managed context)
- Final response handling

The OpenAI Agents SDK `Runner` executes the model/tool loop. This file defines what the agent is allowed to do.

### RAG

Put markdown files into `data/corpus`.

Then run:

```bash
make seed
```

The vector store lives in `chroma_db`.

## Setup

```bash
cp .env.example .env
make install
make run
```

Add your `OPENAI_API_KEY` to `.env` before running the app.
`requests` is included in `requirements.txt` so students can call public HTTP APIs without extra setup.

`make run` seeds the local markdown corpus, then starts Streamlit on port `8503`.

## Exercise Brief

Choose one small application domain. Do not build a large product.

Required tasks:

1. Replace `DomainRecord` in `shared/schemas.py` with fields for your domain.
2. Replace `search_domain_records` in `tools/domain.py` with real logic.
3. Update `SYSTEM_PROMPT` in `model/llm.py`.
4. Adjust tool definitions in `orchestration/agent.py` if your tool needs different arguments.
5. Add at least two markdown files to `data/corpus`.
6. Run `make seed`.
7. Test at least three user questions in Streamlit.

Good demo questions should require the agent to decide between:

- Answering directly.
- Calling the structured domain tool.
- Calling the RAG knowledge tool.
- Calling both tools before answering.

## Suggested Student Applications

- Course assistant: search courses, explain requirements from handbook snippets.
- Event assistant: search events, answer venue or policy questions from local docs.
- Product support assistant: search products, answer support FAQs from markdown.
- Internship helper: search sample internship postings, answer process questions from guidelines.
- Campus service assistant: search services, answer contact and opening-hour questions.
