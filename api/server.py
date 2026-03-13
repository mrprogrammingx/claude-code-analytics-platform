import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict, List, Optional

import duckdb
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.config import DB_PATH

app = FastAPI(title="Claude Telemetry Analytics API")
logger = logging.getLogger("api.server")


def _connect_readonly():
    """Return a new read-only DuckDB connection."""
    try:
        # prefer read-only connections for safety
        return duckdb.connect(str(DB_PATH), read_only=True)
    except duckdb.ConnectionException:
        # If another connection exists with a different configuration (common in tests),
        # fall back to a normal (read-write) connection so queries can still run.
        logger.warning("Failed to open read-only DuckDB connection; falling back to read-write")
        return duckdb.connect(str(DB_PATH))


def exec_query(sql: str, params: Optional[List[Any]] = None, to_dict: bool = True):
    """Execute SQL against DuckDB and return either a DataFrame or list of records.

    - Uses a short-lived connection per call to avoid native handle sharing across threads.
    - Converts to dict only when requested (to save memory/cpu when caller wants raw DF).
    - Raises HTTPException(500) on database errors.
    """
    try:
        con = _connect_readonly()
        if params:
            res = con.execute(sql, params).fetchdf()
        else:
            res = con.execute(sql).fetchdf()
        con.close()
    except Exception as e:
        logger.exception("DuckDB query failed")
        raise HTTPException(status_code=500, detail=str(e))

    if to_dict:
        # Strongly sanitize DataFrame values so JSON encoding cannot fail.
        try:
            # replace infinities with NaN, then convert NaN to None
            res = res.replace([np.inf, -np.inf], np.nan)
            res = res.where(pd.notnull(res), None)

            # Convert values column-wise to Python-native types for JSON serialization.
            # Avoid DataFrame.applymap (deprecated); use Series.map where appropriate.

            def _convert_series(s: pd.Series) -> pd.Series:
                # For object dtype (dicts, nested blobs)
                # keep as-is but sanitize scalars inside later
                if s.dtype == "object":

                    def _conv_obj(v):
                        if v is None:
                            return None
                        # pandas NA
                        if pd.isna(v):
                            return None
                        if isinstance(v, np.generic):
                            try:
                                return v.item()
                            except Exception:
                                try:
                                    return float(v)
                                except Exception:
                                    return None
                        return v

                    return s.map(_conv_obj)

                # For numeric types (float/int), coerce to Python scalars safely
                if pd.api.types.is_integer_dtype(s.dtype):
                    return s.map(lambda x: None if pd.isna(x) else int(x))
                if pd.api.types.is_float_dtype(s.dtype):
                    return s.map(lambda x: None if pd.isna(x) or not np.isfinite(x) else float(x))

                # For datetime-like types, convert to ISO strings
                if pd.api.types.is_datetime64_any_dtype(s.dtype) or isinstance(
                    s.dtype, pd.DatetimeTZDtype
                ):
                    return s.map(lambda x: None if pd.isna(x) else x.isoformat())

                # Fallback: map with NA handling
                return s.map(lambda x: None if pd.isna(x) else x)

            res = pd.concat([_convert_series(res[col]).rename(col) for col in res.columns], axis=1)
        except Exception:
            logger.exception(
                "Failed to fully sanitize DataFrame values; proceeding with best-effort conversion"
            )

        records = res.to_dict(orient="records")

        # final recursive sanitizer to ensure JSON compliance (remove inf/-inf,
        # convert non-serializable)
        def _sanitize_value(v):
            # None
            if v is None:
                return None
            # basic types
            if isinstance(v, (str, bool)):
                return v
            if isinstance(v, int):
                return int(v)
            # floats: ensure finite
            if isinstance(v, float):
                if np.isfinite(v):
                    return float(v)
                return None
            # Decimal
            if isinstance(v, Decimal):
                try:
                    f = float(v)
                    if np.isfinite(f):
                        return f
                    return None
                except Exception:
                    return None
            # numpy scalar
            if isinstance(v, np.generic):
                try:
                    pv = v.item()
                    return _sanitize_value(pv)
                except Exception:
                    return None
            # pandas Timestamp
            try:
                if isinstance(v, pd.Timestamp):
                    return v.isoformat()
            except Exception:
                pass
            # dict/list/tuple -> recurse
            if isinstance(v, dict):
                return {str(k): _sanitize_value(val) for k, val in v.items()}
            if isinstance(v, (list, tuple)):
                return [_sanitize_value(x) for x in v]
            # fallback: use jsonable_encoder and hope for best
            try:
                enc = jsonable_encoder(v)
                return enc
            except Exception:
                return None

        try:
            sanitized = [_sanitize_value(rec) for rec in records]
            return sanitized
        except Exception:
            logger.exception("Failed to sanitize records; returning raw records as fallback")
            return records
    return res


@app.get("/")
def root():
    return {"message": "Claude Telemetry Analytics API"}


@app.get("/health")
def health():
    # quick DB check
    try:
        exec_query("SELECT 1", to_dict=False)
        return {"status": "ok"}
    except HTTPException:
        raise HTTPException(status_code=500, detail="database unreachable")


@app.get("/events")
def events(limit: int = Query(100, ge=1, le=5000)):
    sql = (
        "SELECT id, ts, user_email, event_name, total_tokens "
        "FROM telemetry_events "
        "ORDER BY ts DESC "
        "LIMIT ?"
    )
    return exec_query(sql, params=[limit])


@lru_cache(maxsize=8)
def _metrics_cached() -> List[Dict[str, Any]]:
    sql = (
        "SELECT COUNT(*) AS events, COUNT(DISTINCT user_email) AS users, "
        "SUM(total_tokens) AS total_tokens FROM telemetry_events"
    )
    return exec_query(sql)


@app.get("/metrics")
def metrics():
    # lightweight cached metrics
    return _metrics_cached()


@app.get("/users")
def users(limit: int = Query(50, ge=1, le=1000)):
    sql = (
        "SELECT user_email, COUNT(*) AS events, SUM(COALESCE(total_tokens,0)) AS tokens "
        "FROM telemetry_events WHERE user_email IS NOT NULL GROUP BY user_email "
        "ORDER BY tokens DESC LIMIT ?"
    )
    return exec_query(sql, params=[limit])


@app.get("/analytics/peak-hours")
def peak_hours_dashboard():
    sql = (
        "SELECT EXTRACT(HOUR FROM ts) AS hour, COUNT(*) AS events "
        "FROM telemetry_events GROUP BY hour ORDER BY hour"
    )
    return exec_query(sql)


@app.get("/telemetry")
def get_telemetry(limit: int = Query(100, ge=1, le=10000)):
    # Return JSONResponse (duckdb DataFrame converted to python objects)
    df_records = exec_query("SELECT * FROM telemetry_events LIMIT ?", params=[limit])
    return JSONResponse(content=df_records)
