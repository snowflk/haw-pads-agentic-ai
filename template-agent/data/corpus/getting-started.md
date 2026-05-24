# Template Agent Knowledge Base

This is a small starter knowledge document.

Students should replace this file with markdown documents for their chosen domain.
The RAG tool retrieves chunks from files in `data/corpus` and gives them to the agent as context.

Suggested domains for the exercise:

- Campus service assistant
- Course finder
- Event recommendation assistant
- FAQ assistant for a student project
- Simple product support assistant

When adding new knowledge files, run:

```bash
make seed
```

Then start the app with:

```bash
make run
```
