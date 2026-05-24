# Bundesliga Agent (Student Copy)

This project is a student implementation based on `template-agent`.

Use case:

- Ask for Bundesliga team matches.
- Ask for Bundesliga table standings.
- Optionally use local markdown notes (RAG) for static explanations.

## API Used

- OpenLigaDB docs: `https://api.openligadb.de/index.html`
- Example endpoints:
  - `GET /getmatchdata/{leagueShortcut}/{leagueSeason}/{teamFilterstring}`
  - `GET /getbltable/{leagueShortcut}/{leagueSeason}`

## Architecture

- `model/llm.py`: Bundesliga-oriented system prompt and default model
- `tools/domain.py`: OpenLigaDB API client and data mapping
- `orchestration/agent.py`: tool registration and runtime traces
- `tools/knowledge.py` + `knowledge/vector_store.py`: optional local RAG
- `app.py`: Streamlit UI

## Run

```bash
cd student-openligadb-agent
cp .env.example .env
make install
make run
```

App URL: `http://localhost:8503`

## Example Prompts

- `Show me the latest Hamburg matches in Bundesliga season 2025.`
- `Who are the top 5 teams in bl1 season 2025?`
- `Wann spielt Bayern als nächstes?`

## Notes

- This project intentionally keeps the tool layer small and explicit.
- The model decides which tool to call and with which arguments.
