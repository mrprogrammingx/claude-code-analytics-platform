# Analytics Platform
[![CI](https://github.com/mrprogrammingx/analytics-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/mrprogrammingx/analytics-platform/actions/workflows/ci.yml)
## Quick start (3 minutes, recommended)

Choose one of the two workflows below — Quick start (fast, opinionated) or Manual start (step-by-step). You only need to follow one.

1) Prepare a virtual environment (required for either workflow):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

2) Quick start (recommended): run the full pipeline end-to-end:

```bash
bash scripts/run_pipeline.sh --generate
```

What this does:
- Generate sample telemetry data (writes to `data_generator/output`)
- Run ingestion to populate `analytics.db`
- Launch the Streamlit dashboard

If you already have sample files in `data_generator/output` and only want to ingest + start the dashboard, run:

```bash
bash scripts/run_pipeline.sh --no-generate
```

Advanced: run ingestion directly if you want more control over paths or chunk size:

```bash
python -m ingestion.parse_logs \
	--log-path data_generator/output/telemetry_logs.jsonl \
	--employee-path data_generator/output/employees.csv \
	--db-path analytics.db \
	--chunk-size 500
```

Note: `ingestion.parse_logs` defaults to `data_generator/output` (see `ingestion/parse_logs.py`). The generator creates that folder automatically.

When the dashboard starts, open the URL printed by Streamlit (usually http://localhost:8501).

---

## Manual start (detailed)

Follow these steps if you prefer to run each stage explicitly.

1) Create and activate a virtual environment (same as Quick start):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

2) Generate sample telemetry + employees data (writes to `data_generator/output`):

```bash
python -m data_generator.generate_fake_data
```

3) Run ingestion to populate the DuckDB file (`analytics.db`):

```bash
python -m ingestion.parse_logs
```

You can pass the same advanced flags shown in the Quick start example to control paths or chunk size.

4) Start the Streamlit dashboard:

```bash
streamlit run dashboard/main.py
```

Open the URL printed by Streamlit (usually http://localhost:8501).

---

## Project structure
```
analytics-platform
│
├── app/                         # application config & helpers
├── api/                         # FastAPI endpoints (api/server.py)
├── data_generator/              # fake-data generator and sample output
├── ingestion/                   # ingestion pipeline (parse_logs.py)
├── dashboard/                   # Streamlit dashboard
├── scripts/                     # helper scripts (run_pipeline.sh, demo.sh)
├── tests/                       # pytest unit/integration tests
├── analytics.db                 # DuckDB analytics database (optional/sample)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .pre-commit-config.yaml
├── README.md
└── docs/                        # project docs, LLM usage logs, slides
		├── LLM_USAGE_LOG.md
		├── LLM_USAGE.md
		└── slides/
				└── insights.md
```

## What each piece does

Below is a short, non-redundant summary of the project's main components. See the "Project structure" section above for exact paths.

- data_generator — Fake-data generator that writes sample telemetry JSONL and an `employees.csv` to `data_generator/output`.
- ingestion — ETL pipeline that parses the JSONL, normalizes nested fields, computes timestamps/derived columns, and writes the DuckDB tables (`telemetry_events`, `employees`). See `ingestion/parse_logs.py`.
- dashboard — Streamlit app (`dashboard/main.py`) for interactive exploration, common aggregates, and a safe custom-SQL preview mode.
- api — FastAPI service (`api/server.py`) exposing programmatic endpoints (events, metrics, users, analytics).
- app/config.py — Central configuration (paths, constants, settings) used by other components.
- scripts — Convenience scripts (`scripts/run_pipeline.sh`, `scripts/demo.sh`) to generate data, run ingestion, and launch the demo.

If you prefer a single place to look, the "Project structure" section above lists these components and their primary locations.


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

OpenAPI / Swagger UI

- Interactive API docs (FastAPI OpenAPI): http://localhost:8000/docs

## Predict via the API

Start the API:

```bash
uvicorn api.server:app --reload
```

Send a POST to http://127.0.0.1:8000/predict with JSON:

```json
{"prompt_length": 120, "model": "claude-v1"}
```

or

```json
{"prompt_length": 120, "model_code": 0}
```

Response:

```json
{"prediction": <float>}
```

## Training / Forecasting

The repository includes a tiny trainer used by the demo notebook and examples: `scripts/train_forecast.py`.

What it does:
- Loads a sample of telemetry events from `analytics.db` (if present) or falls back to a synthetic dataset.
- Featurizes `prompt_length` and `model` (the script maps `model` to a categorical code).
- Trains either a scikit-learn RandomForestRegressor (if `scikit-learn` is installed) or a simple linear least-squares fallback.
- Persists the model to `models/forecast.joblib` (joblib if available, otherwise pickle).

Run the trainer from the repository root (recommended inside your virtualenv):

```bash
python -m scripts.train_forecast
```

Result:
- The trained model file is written to `models/forecast.joblib`.
- The demo notebook and the API expect the model at that path. If you run the trainer locally, the API `/predict` endpoint will use the persisted model when available.

Notes:
- Install scikit-learn and joblib in your virtualenv to get a RandomForest model and a joblib-persisted file:

```bash
python -m pip install scikit-learn joblib
```

- If `analytics.db` doesn't exist, the trainer will synthesize data so you can still create a model for the demo.



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

## Continuous Integration (CI) notes

Small details about the repository CI that are helpful when troubleshooting CI failures or updating workflow files:

- Notebook execution: the CI runs `jupyter nbconvert --execute` to run `notebooks/predictive_example.ipynb`. The runner doesn't have a Jupyter kernelspec by default, so the workflow installs `ipykernel` and registers a kernel named `python3` before executing the notebook. If you modify CI notebook steps, keep that kernel registration in place or adjust `--ExecutePreprocessor.kernel_name` accordingly.

- Artifact uploads: the workflow uploads the executed notebook as an artifact. Because the CI runs a matrix of Python versions, artifact uploads include the matrix `python-version` in the artifact name (for example `executed-notebook-3.11`) to avoid conflicts where multiple jobs upload an artifact with the same name.

- Node.js runtime for actions: some GitHub Actions still run on Node.js 20 and GitHub will switch the default Node.js to 24 in the future. The workflow currently opts in to Node.js 24 by setting `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` at the workflow level to avoid deprecation warnings; update or remove this as needed when the actions you use are updated.

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

### Running the demo scripts

The `scripts` folder is a Python package. Prefer running example scripts as a module so the repository root is on `sys.path` and in-repo imports (for example `app.config`) work correctly.

- Combined demo (producer + consumer, 10s):
```bash
python -m scripts.realtime_simulator --mode demo --run-time 10
```

- Producer only:
```bash
python -m scripts.realtime_simulator --mode producer
```

- Consumer only:
```bash
python -m scripts.realtime_simulator --mode consumer
```

Running with `python -m` is recommended for scripts inside the `scripts/` package. Alternatively, if you must run the `.py` file directly, run it from the repository root so imports work (less robust).

### Slides

Slides are stored under `docs/slides/`.


## Architecture (brief)

Data flows from generators (or real sources simulation) into the ingestion pipeline which
normalizes and writes structured tables into a DuckDB file (`analytics.db`).
The Streamlit dashboard and FastAPI service query DuckDB using short-lived
connections; analytic queries and ad-hoc SQL feed the dashboard widgets and
API endpoints. Optional components include a realtime producer/consumer that
appends to a JSONL staging file and a small ML workflow for forecasting.

```
### Deliverables checklist

The repository contains the following deliverables for submission:

- Source code (this repo) with commit history
- `README.md` (this file) with setup & run instructions
- `analytics.db` (sample DuckDB file, optional)
- `notebooks/predictive_example.ipynb` — toy forecasting notebook
- `docs/LLM_USAGE_LOG.md` — LLM usage log
- `docs/slides/insights.md` — short insights slides
- `scripts/realtime_simulator.py` — realtime producer/consumer sketch
- `scripts/train_forecast.py` — small forecasting trainer that persists a model
- `api/server.py` — FastAPI endpoints (including `/predict`)

