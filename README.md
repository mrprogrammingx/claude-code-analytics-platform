# Analytics Platform

An end-to-end Claude Code usage analytics platform. This repository contains:

- A small telemetry fake-data generator (for local testing).
- An ingestion script that parses telemetry JSONL and writes normalized tables into a local DuckDB file (`analytics.db`).
- A Streamlit dashboard for interactive analytics and ad-hoc SQL queries.

---

## Quick start (3 minutes, recommended)
1. Create and activate a virtualenv (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
bash scripts/run_pipeline.sh --no-generate
```
Or
```bash
bash scripts/run_pipeline.sh
```

Note: the ingestion script reads from a data directory defined in `ingestion/parse_logs.py` (default: `data_generator/output`). The generator creates that output folder and files automatically, so there's no need to copy files between directories.

The Streamlit dashboard will start automatically.  
Open the local URL printed by Streamlit (usually http://localhost:8501).

---
## Manual start (Optional)

1. Create and activate a virtualenv (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Generate sample telemetry + employees data (required before ingestion):

```bash
# This script writes sample files into data_generator/output
python3 data_generator/generate_fake_data.py
```

3. Populate the DuckDB analytics database by running the ingestion script:

```bash
python3 ingestion/parse_logs.py
```

Note: the ingestion script reads from a data directory defined in `ingestion/parse_logs.py` (default: `data_generator/output`). The generator creates that output folder and files automatically, so there's no need to copy files between directories.

4. Start the Streamlit dashboard:

```bash
# recommended: run the app from the dashboard package
streamlit run dashboard/app.py
```

Open the local URL printed by Streamlit (usually http://localhost:8501).

---

## Project structure
```
analytics-platform
│
├── data_generator
│   ├── generate_fake_data.py
│   └── output/
│
├── ingestion
│   └── parse_logs.py
│
├── dashboard
│   └── app.py
│
├── scripts
│   └── run_pipeline.sh
│
├── analytics.db
├── requirements.txt
└── README.md
```

## What each piece does

- `data_generator/generate_fake_data.py` — creates a small set of telemetry JSONL and an `employees.csv` so you can exercise the ingestion and dashboard without real logs.
- `ingestion/parse_logs.py` — reads the JSONL, normalizes nested fields (turns dotted keys into underscored columns), coerces numeric fields, computes `ts` (datetime) and `total_tokens`, and writes two DuckDB tables: `telemetry_events` and `employees` in `analytics.db`.
- `dashboard/app.py` — interactive dashboard that reads aggregates from `analytics.db`, offers common pre-made queries and a safe custom-SQL editor (preview mode with LIMIT + cached results).
- `scripts/run_pipeline.sh` — convenience pipeline script that orchestrates the full workflow: optionally generates fake telemetry data, runs the ingestion script to populate `analytics.db`, and launches the Streamlit dashboard.
---

## Tips for speed & stability

- The ingestion script currently loads events into memory. For large datasets, process the JSONL in streaming/batched mode and append into DuckDB to avoid OOM.
- The Streamlit app uses short-lived DuckDB connections and a preview+cache workflow for custom SQL. Use the preview button (with a small limit) to get instant responses, then run the full query if you need all rows.
- If you plan to build dashboards used by multiple people or with very large data, consider materializing aggregates (daily/hourly tokens, model counts) during ingestion so the UI only queries small summary tables.

---

## Troubleshooting

- If the dashboard errors when connecting to `analytics.db`, ensure the file exists in the repository root and is writable.
- If `employees` or `telemetry_events` tables are missing after ingestion, double-check the `LOG_PATH` and `EMPLOYEE_PATH` constants in `ingestion/parse_logs.py` and verify the sample files exist.
- If Streamlit segfaults or crashes intermittently, make sure the app is using short-lived DuckDB connections (the current `dashboard/app.py` uses read-only connections per query).

---

## Development notes

- Keep the top-level module docstring in `ingestion/parse_logs.py` up to date — it documents inputs, outputs, and side-effects.
- If you update ingestion to create materialized tables, update the README and Streamlit queries to use them for better performance.

