VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip
PRECOMMIT=$(VENV)/bin/pre-commit

.PHONY: venv install dev test lint format run-demo docker-build docker-run

venv:
	python -m venv $(VENV)

install: venv
	$(PY) -m pip install --upgrade pip setuptools wheel
	$(PIP) install -r requirements.txt

dev: install
	$(PIP) install -r requirements-dev.txt

test: dev
	$(PY) -m pytest -q

lint: dev
	$(PRECOMMIT) run --all-files

format: dev
	$(PY) -m ruff check . --fix || true
	$(PY) -m isort . || true
	$(PY) -m black . || true

run-demo:
	bash scripts/demo.sh

docker-build:
	docker build -t analytics-platform:latest .

docker-run:
	docker run --rm -p 8501:8501 -p 8000:8000 analytics-platform:latest
