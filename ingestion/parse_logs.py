"""
Telemetry ingestion pipeline.

Responsibilities:
- Parse a JSONL telemetry stream and normalize nested attributes/resources.
- Validate and coerce numeric fields.
- Convert epoch-ms timestamps to datetimes.
- Persist structured data into a DuckDB file for analytics.

Inputs:
- LOG_PATH (default: data_generator/output/telemetry_logs.jsonl) —
JSONL of raw log records.
- EMPLOYEE_PATH (default: data_generator/output/employees.csv) —
optional employees CSV.

Outputs / Side effects:
- Writes/overwrites `telemetry_events`
and (optionally) `employees` tables into analytics.db (DuckDB file).

Dependencies:
- pandas, duckdb, json (standard lib)

Notes / assumptions:
- This script loads events into memory;
for very large inputs you should switch to a streaming/batched approach.
- The script expects `event['message']` to often be a JSON-encoded string;
it handles both string and dict forms.
- Numeric casting is best-effort — invalid values become NULL.

Quick usage:
    python3 -m ingestion.parse_logs

If you want to re-run on a larger dataset, consider:
- Increasing available memory, or
- Processing the JSONL in streamed/batched chunks and appending to DuckDB incrementally.
"""

import argparse
import json

import duckdb
import pandas as pd

from app.config import CHUNK_SIZE, DB_PATH, EMPLOYEE_PATH, LOG_PATH, TABLE_NAMES


def safe_int(val):
    try:
        return int(val)
    except Exception:
        return None


def safe_float(val):
    try:
        return float(val)
    except Exception:
        return None


def normalize_key(k: str) -> str:
    """Normalize dotted keys like 'user.email' -> 'user_email'"""
    if not isinstance(k, str):
        return str(k)
    return k.replace(".", "_")


def process_chunk(chunk_events):
    """Normalize and flatten a list of events, return as DataFrame"""
    processed = []

    for record in chunk_events:
        for event in record.get("logEvents", []):
            raw_message = event.get("message")
            if isinstance(raw_message, str):
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    message = {"body": raw_message}
            else:
                message = raw_message or {}

            id = event.get("id")
            body = message.get("body", {})
            attributes = message.get("attributes", {}) or {}
            resource = message.get("resource", {}) or {}

            # numeric fields
            prompt_length = safe_int(
                attributes.get("prompt_length") or attributes.get("prompt.length")
            )
            input_tokens = safe_int(attributes.get("input_tokens"))
            output_tokens = safe_int(attributes.get("output_tokens"))
            cache_creation_tokens = safe_int(attributes.get("cache_creation_tokens"))
            cache_read_tokens = safe_int(attributes.get("cache_read_tokens"))
            duration_ms = safe_int(attributes.get("duration_ms"))
            cost_usd = safe_float(attributes.get("cost_usd"))

            evt = {
                "id": id,
                "body": body,
                "timestamp": event.get("timestamp"),
                "event_name": attributes.get("event.name"),
                "user_email": attributes.get("user.email"),
                "organization_id": attributes.get("organization.id"),
                "session_id": attributes.get("session.id"),
                "terminal_type": attributes.get("terminal.type"),
                "user_account_uuid": attributes.get("user.account_uuid"),
                "prompt": attributes.get("prompt"),
                "prompt_length": prompt_length,
                "model": attributes.get("model"),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_tokens": cache_creation_tokens,
                "cache_read_tokens": cache_read_tokens,
                "duration_ms": duration_ms,
                "cost_usd": cost_usd,
                "decision": attributes.get("decision"),
                "tool_name": attributes.get("tool_name"),
                # resource
                "resource_host_name": resource.get("host.name"),
                "resource_host_arch": resource.get("host.arch"),
                "resource_os_type": resource.get("os.type"),
                "resource_os_version": resource.get("os.version"),
                "service_name": resource.get("service.name"),
                "service_version": resource.get("service.version"),
                "user_practice": resource.get("user.practice"),
                "user_profile": resource.get("user.profile"),
                "user_serial": resource.get("user.serial"),
                # raw blobs
                "raw_attributes": attributes,
                "raw_resource": resource,
                # top-level record
                "record_owner": record.get("owner"),
                "record_logGroup": record.get("logGroup"),
                "record_logStream": record.get("logStream"),
                "record_subscriptionFilters": record.get("subscriptionFilters"),
                "record_year": record.get("year"),
                "record_month": record.get("month"),
                "record_day": record.get("day"),
            }

            # Flatten attributes
            for k, v in attributes.items():
                nk = normalize_key(k)
                key = f"attr_{nk}"
                if key not in evt:
                    evt[key] = v

            # Flatten resource
            for k, v in resource.items():
                nk = normalize_key(k)
                key = f"res_{nk}"
                if key not in evt:
                    evt[key] = v

            processed.append(evt)

    df_chunk = pd.DataFrame(processed)
    if not df_chunk.empty:
        # add datetime and total_tokens
        df_chunk["ts"] = pd.to_datetime(df_chunk["timestamp"], unit="ms", errors="coerce")
        df_chunk["total_tokens"] = df_chunk["input_tokens"].fillna(0) + df_chunk[
            "output_tokens"
        ].fillna(0)
    return df_chunk


def ingest(log_path: str, employee_path: str, db_path: str, chunk_size: int):
    """Ingest the JSONL at `log_path` into DuckDB at `db_path` using chunked processing."""
    con = duckdb.connect(db_path)
    try:
        con.execute(f"DROP TABLE IF EXISTS {TABLE_NAMES['telemetry']}")

        buffer = []
        count = 0

        with open(log_path) as f:
            print("Reading logs in chunks...")
            for line in f:
                record = json.loads(line)
                buffer.append(record)
                if len(buffer) >= chunk_size:
                    df_chunk = process_chunk(buffer)
                    # skip empty chunks
                    if df_chunk.empty:
                        buffer = []
                        continue

                    # Register DataFrame with DuckDB before executing SQL that references it
                    con.register("df_chunk", df_chunk)

                    if count == 0:
                        # Create table with the first chunk
                        con.execute(
                            f"CREATE TABLE {TABLE_NAMES['telemetry']} AS SELECT * FROM df_chunk"
                        )
                        # Get table columns for later chunks
                        table_cols = [
                            c[0]
                            for c in con.execute(
                                f"PRAGMA table_info('{TABLE_NAMES['telemetry']}')"
                            ).fetchall()
                        ]
                    else:
                        # Make sure df_chunk has all columns (fill missing with NULL)
                        for col in table_cols:
                            if col not in df_chunk.columns:
                                df_chunk[col] = None
                        # Reorder columns to match table
                        df_chunk = df_chunk[table_cols]
                        con.register("df_chunk", df_chunk)
                        con.execute(
                            f"INSERT INTO {TABLE_NAMES['telemetry']} SELECT * FROM df_chunk"
                        )

                    count += len(df_chunk)
                    buffer = []

        # process remaining
        if buffer:
            df_chunk = process_chunk(buffer)
            if not df_chunk.empty:
                con.register("df_chunk", df_chunk)
                if count == 0:
                    con.execute(
                        f"CREATE TABLE IF NOT EXISTS {TABLE_NAMES['telemetry']} AS "
                        "SELECT * FROM df_chunk"
                    )
                    table_cols = [
                        c[0]
                        for c in con.execute(
                            f"PRAGMA table_info('{TABLE_NAMES['telemetry']}')"
                        ).fetchall()
                    ]
                else:
                    for col in table_cols:
                        if col not in df_chunk.columns:
                            df_chunk[col] = None
                    df_chunk = df_chunk[table_cols]
                    con.register("df_chunk", df_chunk)
                    con.execute(f"INSERT INTO {TABLE_NAMES['telemetry']} SELECT * FROM df_chunk")

                count += len(df_chunk)
        print(f"Inserted total {count} events.")

        # create indexes
        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_user_email ON "
            f"{TABLE_NAMES['telemetry']}(user_email)"
        )
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_ts ON {TABLE_NAMES['telemetry']}(ts)")

        # load employees CSV and persist
        try:
            employees_df = pd.read_csv(employee_path)
            con.register("df_employees", employees_df)
            con.execute(f"DROP TABLE IF EXISTS {TABLE_NAMES['employees']}")
            con.execute(f"CREATE TABLE {TABLE_NAMES['employees']} AS SELECT * FROM df_employees")
            print(f"Loaded {employee_path} with {len(employees_df)} rows")
        except FileNotFoundError:
            print(f"{employee_path} not found; skipping employees table creation")
        except Exception as e:
            print(f"Error loading {employee_path}: {e}")
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(description="Ingest telemetry JSONL into DuckDB")
    parser.add_argument("--log-path", default=LOG_PATH, help="Path to telemetry JSONL file")
    parser.add_argument("--employee-path", default=EMPLOYEE_PATH, help="Path to employees CSV")
    parser.add_argument("--db-path", default=DB_PATH, help="Path to DuckDB file")
    parser.add_argument(
        "--chunk-size", type=int, default=CHUNK_SIZE, help="Chunk size for processing"
    )
    args = parser.parse_args()

    ingest(args.log_path, args.employee_path, args.db_path, args.chunk_size)


if __name__ == "__main__":
    main()
