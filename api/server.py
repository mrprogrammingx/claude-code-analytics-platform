import duckdb
from fastapi import FastAPI

from app.config import DB_PATH

app = FastAPI(title="Claude Telemetry Analytics API")


def query(sql):
    con = duckdb.connect(DB_PATH, read_only=True)
    df = con.execute(sql).df()
    con.close()
    return df.to_dict(orient="records")


@app.get("/")
def root():
    return {"message": "Claude Telemetry Analytics API"}


@app.get("/events")
def events(limit: int = 100):
    return query(
        f"""
        SELECT id, ts, user_email, event_name, total_tokens
        FROM telemetry_events
        ORDER BY ts DESC
        LIMIT {limit}
    """
    )


@app.get("/metrics")
def metrics():
    return query(
        """
        SELECT
            COUNT(*) as events,
            COUNT(DISTINCT user_email) as users,
            SUM(total_tokens) as total_tokens
        FROM telemetry_events
    """
    )


@app.get("/users")
def users(limit: int = 50):
    return query(
        f"""
        SELECT
            user_email,
            COUNT(*) AS events,
            SUM(COALESCE(total_tokens,0)) AS tokens
        FROM telemetry_events
        WHERE user_email IS NOT NULL
        GROUP BY user_email
        ORDER BY tokens DESC
        LIMIT {limit}
    """
    )


@app.get("/analytics/peak-hours")
def peak_hours_dashboard():
    return query(
        """
        SELECT EXTRACT(HOUR FROM ts) AS hour, COUNT(*) AS events
        FROM telemetry_events
        GROUP BY hour
        ORDER BY hour
    """
    )
