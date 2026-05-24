PYTHON := .venv/bin/python
PIP := .venv/bin/pip
STREAMLIT := .venv/bin/streamlit

.PHONY: install crawl seed run clean

.venv/bin/python:
	python3 -m venv .venv

install: .venv/bin/python
	$(PIP) install -r requirements.txt

crawl: install
	$(PYTHON) crawl_hibs.py --output-dir data/corpus --max-pages 400

seed: install
	$(PYTHON) seed_chroma.py --corpus-dir data/corpus

run: seed
	$(STREAMLIT) run app.py --server.headless true --server.port 8501

run-fresh: crawl seed
	$(STREAMLIT) run app.py --server.headless true --server.port 8501

clean:
	rm -rf .venv chroma_db data/corpus
