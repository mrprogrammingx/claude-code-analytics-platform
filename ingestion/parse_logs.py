"""
Telemetry ingestion pipeline.

Responsibilities:
- Parse a JSONL telemetry stream and normalize nested attributes/resources.
- Validate and coerce numeric fields.
- Convert epoch-ms timestamps to datetimes.
- Persist structured data into a DuckDB file for analytics.

Inputs:
- LOG_PATH (default: data_generator/output/telemetry_logs.jsonl) — JSONL of raw log records.
- EMPLOYEE_PATH (default: data_generator/output/employees.csv) — optional employees CSV.

Outputs / Side effects:
- Writes/overwrites `telemetry_events` and (optionally) `employees` tables into analytics.db (DuckDB file).

Dependencies:
- pandas, duckdb, json (standard lib)

Notes / assumptions:
- This script loads events into memory; for very large inputs you should switch to a streaming/batched approach.
- The script expects `event['message']` to often be a JSON-encoded string; it handles both string and dict forms.
- Numeric casting is best-effort — invalid values become NULL.

Quick usage:
    python3 ingestion/parse_logs.py

If you want to re-run on a larger dataset, consider:
- Increasing available memory, or
- Processing the JSONL in streamed/batched chunks and appending to DuckDB incrementally.
"""

import json
import duckdb
import pandas as pd
