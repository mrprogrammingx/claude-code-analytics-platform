import importlib
import json
import math
import os
import sys


def _load_parse_logs():
    # Ensure project root is on sys.path so tests can import local packages
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    return importlib.import_module("ingestion.parse_logs")


def test_safe_int():
    pl = _load_parse_logs()
    assert pl.safe_int("123") == 123
    assert pl.safe_int(5) == 5
    assert pl.safe_int("not-an-int") is None
    assert pl.safe_int(None) is None


def test_safe_float():
    pl = _load_parse_logs()
    assert math.isclose(pl.safe_float("1.23"), 1.23)
    # valid float string like 'nan' becomes a float('nan') which is not finite;
    # safe_float returns float('nan')
    nan_val = pl.safe_float("nan")
    assert isinstance(nan_val, float)
    assert math.isnan(nan_val)
    assert pl.safe_float("nope") is None
    assert pl.safe_float(None) is None


def test_normalize_key():
    pl = _load_parse_logs()
    assert pl.normalize_key("user.email") == "user_email"
    assert pl.normalize_key(123) == "123"


def test_process_chunk_minimal():
    pl = _load_parse_logs()
    # Create a minimal record that matches expected structure
    record = {
        "logEvents": [
            {
                "id": "evt1",
                "message": json.dumps(
                    {
                        "body": {"text": "hi"},
                        "attributes": {
                            "user.email": "a@b.com",
                            "input_tokens": "2",
                            "output_tokens": "3",
                        },
                        "resource": {"host.name": "host1"},
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

    df = pl.process_chunk([record])
    assert not df.empty
    row = df.iloc[0]
    assert row["id"] == "evt1"
    assert row["user_email"] == "a@b.com"
    # total_tokens should be 2 + 3 = 5
    assert int(row["total_tokens"]) == 5
