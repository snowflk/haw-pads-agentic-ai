PYTHON := .venv/bin/python
PIP := .venv/bin/pip
STREAMLIT := .venv/bin/streamlit

.PHONY: install seed run clean

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

seed:
	$(PYTHON) seed_chroma.py

run: seed
	$(STREAMLIT) run app.py --server.port 8503

clean:
	rm -rf .venv chroma_db agent_sessions.db __pycache__ */__pycache__
