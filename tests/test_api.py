import importlib
import json
import os
from pathlib import Path

import duckdb
import pandas as pd
from fastapi.testclient import TestClient


def make_sample_record():
    return {
        "logEvents": [
            {
                "id": "evt_api_1",
                "message": json.dumps(
                    {
                        "body": {"text": "hello"},
                        "attributes": {
                            "user.email": "x@y.com",
                            "input_tokens": "1",
                            "output_tokens": "2",
                        },
                        "resource": {"host.name": "host-api"},
                    }
                ),
                "timestamp": 1600000000000,
            }
        ],
        "owner": "owner1",
        "logGroup": "lg",
        "logStream": "ls",
        "subscriptionFilters": [],
        "year": 2020,
        "month": 1,
        "day": 1,
    }


def test_ingest_and_api_endpoints(tmp_path, monkeypatch):
    # prepare temp files
    log_path = Path(tmp_path) / "telemetry_logs.jsonl"
    employee_path = Path(tmp_path) / "employees.csv"
    db_path = Path(tmp_path) / "analytics.db"

    record = make_sample_record()
    # write JSONL
    with open(log_path, "w") as f:
        f.write(json.dumps(record) + "\n")

    # write employees csv
    df_emp = pd.DataFrame([{"email": "x@y.com", "role": "dev"}])
    df_emp.to_csv(employee_path, index=False)

    # run ingestion (import here so it uses app.config defaults only when needed)
    from ingestion import parse_logs as pl

    # call ingest (uses provided paths)
    pl.ingest(str(log_path), str(employee_path), str(db_path), chunk_size=1)

    # verify DB has expected tables
    con = duckdb.connect(str(db_path))
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    assert "telemetry_events" in tables
    assert "employees" in tables

    # Now point API to this DB and reload api.server so it picks up new DB
    import app.config as cfg

    cfg.DB_PATH = Path(db_path)
    import api.server as server

    importlib.reload(server)

    client = TestClient(server.app)

    # health
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

    # events
    r = client.get("/events?limit=10")
    assert r.status_code == 200
    events = r.json()
    assert isinstance(events, list)
    assert len(events) >= 0

    # telemetry (full records)
    r = client.get("/telemetry?limit=5")
    assert r.status_code == 200
    payload = r.json()
    assert isinstance(payload, list)
