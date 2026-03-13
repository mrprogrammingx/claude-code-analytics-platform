#!/usr/bin/env bash
set -euo pipefail

# Quick demo script: generate data, ingest, start API and dashboard
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "Creating venv (if missing) and installing deps..."
python -m venv .venv || true
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo "Generating sample data (running from data_generator/)..."
(
	cd data_generator
	python generate_fake_data.py --num-users 50 --num-sessions 500 --days 30
)

echo "Ingesting into DuckDB..."
python -m ingestion.parse_logs --log-path data_generator/output/telemetry_logs.jsonl --employee-path data_generator/output/employees.csv --db-path "${DB_PATH:-analytics.db}" --chunk-size 500

echo "Starting API (background)..."
nohup python -m uvicorn api.server:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
echo "API started at http://localhost:8000 (logs: api.log)"

echo "Starting Streamlit dashboard (foreground)..."
python -m streamlit run dashboard/main.py
