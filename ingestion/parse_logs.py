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


DATA_DIR = "data_generator/output"
LOG_PATH = f"{DATA_DIR}/telemetry_logs.jsonl"
EMPLOYEE_PATH = f"{DATA_DIR}/employees.csv"
DB_PATH = "analytics.db"
CHUNK_SIZE = 10_000_000  # adjust based on memory

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
    return k.replace('.', '_')


# Connect to DuckDB once
con = duckdb.connect(DB_PATH)
con.execute('DROP TABLE IF EXISTS telemetry_events')

def process_chunk(chunk_events):
    """Normalize and flatten a list of events, return as DataFrame"""
    processed = []

    for record in chunk_events:
        for event in record.get('logEvents', []):
            raw_message = event.get('message')
            if isinstance(raw_message, str):
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    message = {'body': raw_message}
            else:
                message = raw_message or {}

            id = event.get('id')
            body = message.get('body', {})
            attributes = message.get('attributes', {}) or {}
            resource = message.get('resource', {}) or {}

            # numeric fields
            prompt_length = safe_int(attributes.get('prompt_length') or attributes.get('prompt.length'))
            input_tokens = safe_int(attributes.get('input_tokens'))
            output_tokens = safe_int(attributes.get('output_tokens'))
            cache_creation_tokens = safe_int(attributes.get('cache_creation_tokens'))
            cache_read_tokens = safe_int(attributes.get('cache_read_tokens'))
            duration_ms = safe_int(attributes.get('duration_ms'))
            cost_usd = safe_float(attributes.get('cost_usd'))

            evt = {
                'id': id,
                'body': body,
                'timestamp': event.get('timestamp'),
                'event_name': attributes.get('event.name'),
                'user_email': attributes.get('user.email'),
                'organization_id': attributes.get('organization.id'),
                'session_id': attributes.get('session.id'),
                'terminal_type': attributes.get('terminal.type'),
                'user_account_uuid': attributes.get('user.account_uuid'),
                'prompt': attributes.get('prompt'),
                'prompt_length': prompt_length,
                'model': attributes.get('model'),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cache_creation_tokens': cache_creation_tokens,
                'cache_read_tokens': cache_read_tokens,
                'duration_ms': duration_ms,
                'cost_usd': cost_usd,
                'decision': attributes.get('decision'),
                'tool_name': attributes.get('tool_name'),
                # resource
                'resource_host_name': resource.get('host.name'),
                'resource_host_arch': resource.get('host.arch'),
                'resource_os_type': resource.get('os.type'),
                'resource_os_version': resource.get('os.version'),
                'service_name': resource.get('service.name'),
                'service_version': resource.get('service.version'),
                'user_practice': resource.get('user.practice'),
                'user_profile': resource.get('user.profile'),
                'user_serial': resource.get('user.serial'),
                # raw blobs
                'raw_attributes': attributes,
                'raw_resource': resource,
                # top-level record
                'record_owner': record.get('owner'),
                'record_logGroup': record.get('logGroup'),
                'record_logStream': record.get('logStream'),
                'record_subscriptionFilters': record.get('subscriptionFilters'),
                'record_year': record.get('year'),
                'record_month': record.get('month'),
                'record_day': record.get('day'),
            }

            # Flatten attributes
            for k, v in attributes.items():
                nk = normalize_key(k)
                key = f'attr_{nk}'
                if key not in evt:
                    evt[key] = v

            # Flatten resource
            for k, v in resource.items():
                nk = normalize_key(k)
                key = f'res_{nk}'
                if key not in evt:
                    evt[key] = v

            processed.append(evt)

    df_chunk = pd.DataFrame(processed)
    if not df_chunk.empty:
        # add datetime and total_tokens
        df_chunk['ts'] = pd.to_datetime(df_chunk['timestamp'], unit='ms', errors='coerce')
        df_chunk['total_tokens'] = (
            df_chunk['input_tokens'].fillna(0) + df_chunk['output_tokens'].fillna(0)
        )
    return df_chunk

buffer = []
count = 0

with open(LOG_PATH) as f:
    print("Reading logs in chunks...")
    for line in f:
        record = json.loads(line)
        buffer.append(record)
        if len(buffer) >= CHUNK_SIZE:
            df_chunk = process_chunk(buffer)
            if count == 0:
                # Create table with the first chunk
                con.execute("CREATE TABLE telemetry_events AS SELECT * FROM df_chunk")
                # Get table columns for later chunks
                table_cols = [c[0] for c in con.execute("PRAGMA table_info('telemetry_events')").fetchall()]
            else:
                # Make sure df_chunk has all columns (fill missing with NULL)
                for col in table_cols:
                    if col not in df_chunk.columns:
                        df_chunk[col] = None
                # Reorder columns to match table
                df_chunk = df_chunk[table_cols]
                con.execute("INSERT INTO telemetry_events SELECT * FROM df_chunk")

            count += len(df_chunk)

# process remaining
if buffer:
    df_chunk = process_chunk(buffer)
    con.execute("CREATE TABLE IF NOT EXISTS telemetry_events AS SELECT * FROM df_chunk") if count==0 else con.execute("INSERT INTO telemetry_events SELECT * FROM df_chunk")
    count += len(df_chunk)
    print(f"Inserted total {count} events.")


# create indexes
con.execute("CREATE INDEX idx_user_email ON telemetry_events(user_email)")
con.execute("CREATE INDEX idx_ts ON telemetry_events(ts)")


# load employees CSV and persist
try:
    employees_df = pd.read_csv(EMPLOYEE_PATH)
    con.register('df_employees', employees_df)
    con.execute('DROP TABLE IF EXISTS employees')
    con.execute('CREATE TABLE employees AS SELECT * FROM df_employees')
    print(f"Loaded employees.csv with {len(employees_df)} rows")
except FileNotFoundError:
    print(f"employees.csv not found at {EMPLOYEE_PATH}; skipping employees table creation")
except Exception as e:
    print(f"Error loading employees.csv: {e}")

con.close()