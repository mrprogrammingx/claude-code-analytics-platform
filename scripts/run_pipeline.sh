#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# scripts/run_pipeline.sh
# Usage:
#   bash scripts/run_pipeline.sh --generate          # generate data, ingest, run dashboard
#   bash scripts/run_pipeline.sh --no-generate
#   bash scripts/run_pipeline.sh -n

GENERATE=false

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --no-generate|-n)
      GENERATE=false
      shift
      ;;
    --generate|-g)
      GENERATE=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--no-generate|-n]"
      echo "       $0 [--generate|-g]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--no-generate|-n]"
      exit 1
      ;;
  esac
done

if [ "$GENERATE" = true ]; then
  echo "Preparing output directory..."
  mkdir -p data_generator/output

  echo "Generating telemetry data..."
  (
    cd data_generator
    python3 generate_fake_data.py --num-users 50 --num-sessions 2500 --days 32
  )
else
  echo "Skipping data generation"
fi

echo "Running ingestion pipeline..."
python3 ingestion/parse_logs.py

echo "Starting analytics dashboard..."
# use exec so the dashboard process inherits the PID (nice for ctrl-c)
exec python3 -m streamlit run dashboard/app.py
