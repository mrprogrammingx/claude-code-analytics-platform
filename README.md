# Analytics Platform
[![CI](https://github.com/mrprogrammingx/analytics-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/mrprogrammingx/analytics-platform/actions/workflows/ci.yml)

An end-to-end Claude Code usage analytics platform. This repository contains:

- A small telemetry fake-data generator (for local testing).
- An ingestion script that parses telemetry JSONL and writes normalized tables into a local DuckDB file (`analytics.db`).
- A Streamlit dashboard for interactive analytics and ad-hoc SQL queries.

---

## Quick start (3 minutes, recommended)
1. Create and activate a virtualenv (recommended):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

2. Run the full pipeline (recommended):

```bash
bash scripts/run_pipeline.sh --generate
```
This will:
- Generate sample telemetry data
- Run the ingestion pipeline
- Start the Streamlit dashboard

If the sample data already exists and you only want to ingest + start the dashboard:

### Populate the DuckDB analytics database by running the ingestion script:
```bash
# Run the pipeline but skip data generation (use existing data in data_generator/output)
bash scripts/run_pipeline.sh --no-generate
```
python -m ingestion.parse_logs --log-path data_generator/output/telemetry_logs.jsonl --employee-path data_generator/output/employees.csv --db-path analytics.db --chunk-size 500
```bash
python3 -m ingestion.parse_logs --log-path data_generator/output/telemetry_logs.jsonl --employee-path data_generator/output/employees.csv --db-path analytics.db --chunk-size 500
```

Note: the ingestion script reads from a data directory defined in `ingestion/parse_logs.py` (default: `data_generator/output`). The generator creates that output folder and files automatically, so there's no need to copy files between directories.

The Streamlit dashboard will start automatically.  
Open the local URL printed by Streamlit (usually http://localhost:8501).

---
## Manual start (Optional)

python -m venv .venv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Generate sample telemetry + employees data (required before ingestion):
python -m data_generator.generate_fake_data
```bash
# This script writes sample files into data_generator/output
python3 -m data_generator.generate_fake_data
```

python -m ingestion.parse_logs

```bash
python3 -m ingestion.parse_logs
```

Note: the ingestion script reads from a data directory defined in `ingestion/parse_logs.py` (default: `data_generator/output`). The generator creates that output folder and files automatically, so there's no need to copy files between directories.

4. Start the Streamlit dashboard:

```bash
# recommended: run the app from the dashboard package
streamlit run dashboard/main.py
```

Open the local URL printed by Streamlit (usually http://localhost:8501).

---

## Project structure
```
analytics-platform
│
├── app
│   └── config.py                 # configs for the app
│
├── api
│   └── server.py                # FastAPI service exposing analytics endpoints
│
├── data_generator
│   ├── generate_fake_data.py    # Generates simulated telemetry data
│   └── output/                  # Generated JSONL logs and employees CSV
│
├── ingestion
│   └── parse_logs.py            # Parses telemetry logs and loads DuckDB
│
├── dashboard
│   └── main.py                   # Streamlit analytics dashboard
│
├── scripts
│   └── run_pipeline.sh          # Runs full pipeline (generate → ingest)
│
├── tests
│   └── test_ingest_helpers.py    # unit tests (pytest)
│
├── analytics.db                 # DuckDB analytics database
├── requirements.txt             # Python dependencies
├── requirements-dev.txt         # Python development dependencies
├── pyproject.toml              # the standard configuration file for modern Python projects
├── .gitignore                   # Ignore files and folder for pushing to git
├── .github
│   └── workflows
│       └── ci.yml               # GitHub Actions workflow (CI)
│
├── .pre-commit-config.yaml      # pre-commit hooks configuration (black/ruff/isort)
├── README.md                    # Project documentation
└── docs/
	├── LLM_USAGE_LOG.md        # (Optional) Log of AI tools and prompts used
	└── LLM_USAGE.md            # Summary of LLM usage
```

## What each piece does

- `data_generator/generate_fake_data.py` — creates a small set of telemetry JSONL and an `employees.csv` so you can exercise the ingestion and dashboard without real logs.
- `ingestion/parse_logs.py` — reads the JSONL, normalizes nested fields (turns dotted keys into underscored columns), coerces numeric fields, computes `ts` (datetime) and `total_tokens`, and writes two DuckDB tables: `telemetry_events` and `employees` in `analytics.db`.
- `dashboard/main.py` — interactive dashboard that reads aggregates from `analytics.db`, offers common pre-made queries and a safe custom-SQL editor (preview mode with LIMIT + cached results).
- `scripts/run_pipeline.sh` — convenience pipeline script that orchestrates the full workflow: optionally generates fake telemetry data, runs the ingestion script to populate `analytics.db`, and launches the Streamlit dashboard.
- `api/server.py` — The platform also exposes a lightweight REST API for programmatic access to the analytics data.
- `app/config.py` - Central configuration (paths, constants, settings)
---

## API Access

The platform also exposes a lightweight REST API for programmatic access to the analytics data.

Run:

```bash
uvicorn api.server:app --reload
```

Available endpoints:

GET /events — recent telemetry events  
GET /metrics — aggregated platform metrics  
GET /users — top users by token usage   
GET /analytics/peak-hours - Peak hours for events   
Interactive documentation is available at:

http://localhost:8000/docs

## Tips for speed & stability

- The ingestion script currently loads events into memory. For large datasets, process the JSONL in streaming/batched mode and append into DuckDB to avoid OOM.
- The Streamlit app uses short-lived DuckDB connections and a preview+cache workflow for custom SQL. Use the preview button (with a small limit) to get instant responses, then run the full query if you need all rows.
- If you plan to build dashboards used by multiple people or with very large data, consider materializing aggregates (daily/hourly tokens, model counts) during ingestion so the UI only queries small summary tables.

---

## Troubleshooting

- If the dashboard errors when connecting to `analytics.db`, ensure the file exists in the repository root and is writable.
- If `employees` or `telemetry_events` tables are missing after ingestion, double-check the `LOG_PATH` and `EMPLOYEE_PATH` constants in `ingestion/parse_logs.py` and verify the sample files exist.
- If Streamlit segfaults or crashes intermittently, make sure the app is using short-lived DuckDB connections (the current `dashboard/main.py` uses read-only connections per query).

---
### Code style

This project uses:

- **Black** for formatting
- **Ruff** for linting
- **isort** for import sorting

Run formatting:

```bash
ruff check . --fix
isort .
black .
```

## Dependencies

- Python 3.13 (tested)
- All Python dependencies required to run this project are listed in `requirements.txt`.  
You can install them using:

```bash
pip install -r requirements.txt
```

## Running tests

Unit tests live under the `tests/` directory and use `pytest`.

1. Install development dependencies (recommended inside your virtualenv):

```bash
python -m pip install -r requirements-dev.txt
```

2. Run the full test suite:

```bash
python -m pytest -q
```

3. Run a single test file or test function:

```bash
pytest tests/test_ingest_helpers.py::test_process_chunk_minimal -q
```

The CI (if enabled) will run the same test commands on push/PR. If you discover test import issues, ensure your project root is on `PYTHONPATH` or run tests from the repository root.

### Pre-commit (recommended)

To avoid CI failures after push, install `pre-commit` and enable the local hooks. These hooks run `black`, `ruff`, and `isort` on each commit.

1. Install pre-commit (in your virtualenv):
```bash
python -m pip install pre-commit
```

2. Install the git hooks:

```bash
pre-commit install
```

3. Optionally run the hooks over all files once (this may modify files):

```bash
pre-commit run --all-files -v
```

If pre-commit reformats files, add and commit the changes before pushing so CI sees the same tree.

## Development notes

- Keep the top-level module docstring in `ingestion/parse_logs.py` up to date — it documents inputs, outputs, and side-effects.
- If you update ingestion to create materialized tables, update the README and Streamlit queries to use them for better performance.


### LLM Usage

A detailed log of how AI tools were used in this project is available in the [`LLM_USAGE_LOG.md`](LLM_USAGE_LOG.md) file.  
A detailed log of how AI tools were used in this project is available in the [`docs/LLM_USAGE_LOG.md`](docs/LLM_USAGE_LOG.md) file.  

## Demo script & Docker

We provide a quick demo script and a Dockerfile for reproducible demos.

- `scripts/demo.sh` — Bootstraps a venv (if missing), generates sample data inside `data_generator/output`, runs ingestion into `analytics.db`, starts the API in the background (logs to `api.log`) and launches the Streamlit dashboard.
	- Important: the generator runs from inside `data_generator/` so output files are created in `data_generator/output` (not the repository root).

- Docker: build a demo-ready image that pre-generates sample data and pre-runs ingestion so the image contains `analytics.db`:

```bash
# build
docker build -t analytics-platform:latest .

# run (dashboard is exposed on 8501, API on 8000)
docker run --rm -p 8501:8501 -p 8000:8000 analytics-platform:latest
```

Note: pre-generating data during image build increases build time and image size. If you prefer a minimal image, remove the pre-generation `RUN` steps in the `Dockerfile` and run `demo.sh` inside the container instead.

