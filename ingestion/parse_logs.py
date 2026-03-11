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


# NOTE: For very large datasets this should be processed in batches and/or using a streaming approach instead of loading everything into memory at once.
events = []

with open(LOG_PATH) as f:
    print("Reading logs...")
    for line in f:
        record = json.loads(line)

        for event in record.get('logEvents', []):
            # event['message'] is a JSON-encoded string in the sample data; handle both str and dict
            raw_message = event.get('message')
            if isinstance(raw_message, str):
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    # if it's not valid json, keep it as raw string
                    message = {'body': raw_message}
            else:
                message = raw_message or {}

            # event id in the outer JSON is already a string (not JSON-encoded); don't json.loads it
            id = event.get('id')

            # print(f"Processing event {id}...")

            body = message.get('body', {})
            attributes = message.get('attributes', {}) or {}
            resource = message.get('resource', {}) or {}

            # pull common numeric fields and try to cast them
            prompt_length = safe_int(attributes.get('prompt_length') or attributes.get('prompt.length'))
            input_tokens = safe_int(attributes.get('input_tokens'))
            output_tokens = safe_int(attributes.get('output_tokens'))
            cache_creation_tokens = safe_int(attributes.get('cache_creation_tokens'))
            cache_read_tokens = safe_int(attributes.get('cache_read_tokens'))
            duration_ms = safe_int(attributes.get('duration_ms'))
            cost_usd = safe_float(attributes.get('cost_usd'))
            # base event dict with explicit, commonly used fields
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
                # rich/optional fields
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
                # resource fields (explicit)
                'resource_host_name': resource.get('host.name'),
                'resource_host_arch': resource.get('host.arch'),
                'resource_os_type': resource.get('os.type'),
                'resource_os_version': resource.get('os.version'),
                'service_name': resource.get('service.name'),
                'service_version': resource.get('service.version'),
                'user_practice': resource.get('user.practice'),
                'user_profile': resource.get('user.profile'),
                'user_serial': resource.get('user.serial'),
                # keep raw blobs for debugging if needed
                'raw_attributes': attributes,
                'raw_resource': resource,
            }

            # Flatten all attributes into the event with an 'attr_' prefix, normalizing dots to underscores.
            for k, v in attributes.items():
                nk = normalize_key(k)
                key = f'attr_{nk}'
                # don't overwrite explicit fields
                if key not in evt:
                    evt[key] = v

            # Flatten all resource fields into the event with a 'res_' prefix
            for k, v in resource.items():
                nk = normalize_key(k)
                key = f'res_{nk}'
                if key not in evt:
                    evt[key] = v

            # Include top-level record metadata if available
            evt['record_owner'] = record.get('owner')
            evt['record_logGroup'] = record.get('logGroup')
            evt['record_logStream'] = record.get('logStream')
            evt['record_subscriptionFilters'] = record.get('subscriptionFilters')
            evt['record_year'] = record.get('year')
            evt['record_month'] = record.get('month')
            evt['record_day'] = record.get('day')

            events.append(evt)

df = pd.DataFrame(events)

# normalize timestamp and add a datetime column for easier analysis and also calculate total tokens as a common metric
if not df.empty:
    print(f"Loaded {len(df)} telemetry events")

    # timestamp in the logs is epoch milliseconds
    df['ts'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
    df['total_tokens'] = (
        df['input_tokens'].fillna(0) +
        df['output_tokens'].fillna(0)
    )


con = duckdb.connect(DB_PATH)

# register and persist telemetry events into DuckDB for future analyses
con.register('df_events', df)
con.execute('DROP TABLE IF EXISTS telemetry_events')
con.execute('CREATE TABLE telemetry_events AS SELECT * FROM df_events')

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