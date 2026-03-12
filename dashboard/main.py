import os
import re
import shutil
import tempfile

import duckdb
import pandas as pd
import streamlit as st

from app.config import DANGEROUS_SQL_KEYWORDS, DB_PATH

st.set_page_config(page_title="Telemetry Analytics", layout="wide")


def get_db_path() -> str:
    return DB_PATH


def load_tables():
    db = get_db_path()
    if not os.path.exists(db):
        return []
    with duckdb.connect(db) as c:
        tables = [
            r[0]
            for r in c.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        ]
    return tables


def load_events():
    db = get_db_path()
    try:
        with duckdb.connect(db) as c:
            df = c.execute("SELECT * FROM telemetry_events").fetchdf()
        return df
    except Exception:
        return pd.DataFrame()


def load_employees():
    db = get_db_path()
    try:
        with duckdb.connect(db) as c:
            df = c.execute("SELECT * FROM employees").fetchdf()
        return df
    except Exception:
        return pd.DataFrame()


def detect_email_col(df: pd.DataFrame):
    # common email column names
    for c in ["email", "user_email", "user.email", "user_email_address"]:
        if c in df.columns:
            return c
    # fallback: try any column containing 'email'
    for c in df.columns:
        if "email" in c.lower():
            return c
    return None


def detect_role_col(df: pd.DataFrame):
    # common role/practice column names (include user_practice which your data uses)
    for c in [
        "role",
        "user_role",
        "job_role",
        "position",
        "user_practice",
        "practice",
        "user.practice",
    ]:
        if c in df.columns:
            return c
    for c in df.columns:
        if "role" in c.lower() or "title" in c.lower():
            return c
    return None


def main():
    st.title("Claude Code Telemetry — Analytics")

    tables = load_tables()

    st.sidebar.header("Database")
    st.sidebar.write("Tables:")
    st.sidebar.write(tables)

    events_df = load_events()
    emp_df = load_employees()

    st.markdown("## Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Events", len(events_df))
    c2.metric("Employees", len(emp_df))
    # total tokens if present
    total_output = None
    if "output_tokens" in events_df.columns:
        try:
            total_output = events_df["output_tokens"].dropna().astype(float).sum()
        except Exception:
            total_output = None
    c3.metric("Output tokens (sum)", int(total_output) if total_output is not None else "N/A")

    if "total_tokens" in events_df.columns:
        try:
            total_tokens = events_df["total_tokens"].dropna().astype(float).sum()
        except Exception:
            total_tokens = None
    c4.metric("Total tokens (sum)", int(total_tokens) if total_tokens is not None else "N/A")

    if "timestamp" in events_df.columns:
        try:
            # convert timestamp correctly (milliseconds or nanoseconds)
            events_df["timestamp"] = pd.to_datetime(events_df["timestamp"], unit="ms")

            delta = events_df["timestamp"].max() - events_df["timestamp"].min()
            start = events_df["timestamp"].min()
            end = events_df["timestamp"].max()

            # compute years, months, days
            years = end.year - start.year
            months = end.month - start.month
            days = end.day - start.day
            if days < 0:
                months -= 1
                # get days in previous month
                import calendar

                prev_month = (end.month - 1) if end.month > 1 else 12
                prev_year = end.year if end.month > 1 else end.year - 1
                days += calendar.monthrange(prev_year, prev_month)[1]
            if months < 0:
                years -= 1
                months += 12

            # hours, minutes, seconds
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            # build compact string
            total_duration_str = ""
            if years > 0:
                total_duration_str += f"{years}y "
            if months > 0:
                total_duration_str += f"{months}mo "
            if days > 0:
                total_duration_str += f"{days}d "
            if hours > 0:
                total_duration_str += f"{hours}h "
            if minutes > 0:
                total_duration_str += f"{minutes}m "
            if seconds > 0:
                total_duration_str += f"{seconds}s"

            # fallback
            total_duration_str = total_duration_str.strip() or "0s"

        except Exception:
            total_duration_str = "N/A"

    c5.metric("Total Duration", total_duration_str)

    st.markdown("---")

    # Events over time
    st.markdown("### Events over time")
    if "ts" in events_df.columns:
        ts_df = events_df.copy()
        ts_df["ts_day"] = pd.to_datetime(ts_df["ts"]).dt.floor("D")
        times = ts_df.groupby("ts_day").size().reset_index(name="count")
        st.line_chart(times.rename(columns={"ts_day": "index"}).set_index("index"))
    else:
        st.info("No timestamp column 'ts' found in telemetry_events")

    # Token consumption by role (if employees present)
    st.markdown("### Token consumption by role")
    if not emp_df.empty and not events_df.empty:
        email_col = detect_email_col(emp_df)
        role_col = detect_role_col(emp_df)

        # choose join keys from events: prefer user_email,
        # then attr_user_email, then user_account_uuid
        if "user_email" in events_df.columns and email_col:
            merged = events_df.merge(emp_df, left_on="user_email", right_on=email_col, how="left")
        elif "attr_user_email" in events_df.columns and email_col:
            merged = events_df.merge(
                emp_df, left_on="attr_user_email", right_on=email_col, how="left"
            )
        else:
            merged = events_df

        # Determine which column to use as 'role' for grouping
        role_to_use = None
        if role_col and role_col in merged.columns:
            role_to_use = role_col
        # fallback: event-level resource/user_practice columns
        elif "user_practice" in merged.columns:
            role_to_use = "user_practice"
        elif "res_user_practice" in merged.columns:
            role_to_use = "res_user_practice"

        if role_to_use and "output_tokens" in merged.columns:
            # coerce numeric
            merged["output_tokens_num"] = pd.to_numeric(merged["output_tokens"], errors="coerce")
            by_role = (
                merged.groupby(role_to_use)["output_tokens_num"]
                .sum()
                .dropna()
                .sort_values(ascending=False)
            )
            st.bar_chart(by_role)
        else:
            st.info("Employees or role column not detected, or no output_tokens column available")
    else:
        st.info("Employees table or events table is empty; run ingestion script first")

    st.markdown("---")

    # Top users
    st.markdown("### Top users by events")
    if "user_email" in events_df.columns:
        top_users = events_df["user_email"].value_counts().head(20)
        st.table(
            top_users.reset_index().rename(columns={"index": "user_email", "user_email": "events"})
        )
    else:
        st.info("No user_email column found in telemetry_events")

    st.markdown("---")
    st.markdown("---")

    st.markdown("### Common analytics queries")
    predefined = {
        "Token consumption trends": (
            "SELECT\n  DATE(ts) AS day,\n  SUM(total_tokens) AS tokens\n"
            "FROM telemetry_events\nGROUP BY day\nORDER BY day;"
        ),
        "Usage by seniority": (
            "SELECT\n  e.level,\n  SUM(t.total_tokens) AS tokens\n"
            "FROM telemetry_events t\n"
            "JOIN employees e\n  ON t.user_email = e.email\nGROUP BY e.level;"
        ),
        "Peak usage hours": (
            "SELECT\n  EXTRACT(hour FROM ts) AS hour,\n  "
            "COUNT(*) AS events\n"
            "FROM telemetry_events\n"
            "GROUP BY hour\nORDER BY events DESC;"
        ),
        "Most used models": (
            "SELECT\n  model_norm AS model,\n  COUNT(*) AS usage\nFROM "
            "(\n  SELECT lower(coalesce("
            "NULLIF(trim(model), ''), "
            "NULLIF(trim(attr_model), ''), "
            "NULLIF(trim(model_name), ''))) "
            "AS model_norm\n  FROM telemetry_events\n)"
            " t\nWHERE model_norm IS NOT NULL\nGROUP BY model_norm\nORDER BY usage DESC;"
        ),
    }

    choice = st.selectbox("Choose a query", list(predefined.keys()))
    sql = predefined[choice]
    st.code(sql, language="sql")
    if st.button("Run query"):
        try:
            # If the chosen query is 'Most used models',
            # dynamically build SQL based on available columns
            if choice == "Most used models":
                # get columns for telemetry_events
                db = get_db_path()
                with duckdb.connect(db) as c:
                    cols = [
                        r[0]
                        for r in c.execute(
                            "SELECT column_name FROM "
                            "information_schema.columns "
                            "WHERE table_name='telemetry_events' "
                            "AND table_schema='main'"
                        ).fetchall()
                    ]
                # candidate columns to look for (order of preference)
                candidates = [
                    "model",
                    "attr_model",
                    "model_name",
                    "attr_model_name",
                    "model.name",
                ]
                available = [c for c in candidates if c in cols]
                if not available:
                    st.info("No model-like columns found in telemetry_events")
                    skip_query = True
                else:
                    skip_query = False
                # build coalesce list safely
                coalesce_parts = ", ".join([f"NULLIF(trim({c}), '')" for c in available])
                sql = (
                    "SELECT model_norm AS model, COUNT(*) AS usage FROM ("
                    f"  SELECT lower(coalesce({coalesce_parts}))"
                    f" AS model_norm FROM telemetry_events"
                    ") t WHERE model_norm IS NOT NULL GROUP BY model_norm ORDER BY usage DESC;"
                )

            if choice == "Most used models" and skip_query:
                dfq = pd.DataFrame()
            else:
                # run and fetch using a short-lived connection
                db = get_db_path()
                with duckdb.connect(db) as c:
                    dfq = c.execute(sql).fetchdf()
            if dfq.empty:
                st.info("Query returned no rows")
            else:
                # choose a visualization based on the chosen query
                if choice == "Token consumption trends":
                    # ensure day is datetime
                    if "day" in dfq.columns:
                        dfq["day"] = pd.to_datetime(dfq["day"])
                        st.line_chart(dfq.set_index("day"))
                    else:
                        st.dataframe(dfq)
                elif choice == "Usage by seniority":
                    # if level column missing, try alternative columns
                    if "level" in dfq.columns:
                        st.bar_chart(dfq.set_index("level"))
                    else:
                        st.dataframe(dfq)
                elif choice == "Peak usage hours":
                    if "hour" in dfq.columns:
                        dfq = dfq.sort_values("hour")
                        st.bar_chart(dfq.set_index("hour"))
                    else:
                        st.dataframe(dfq)
                elif choice == "Most used models":
                    if "model" in dfq.columns:
                        st.bar_chart(dfq.set_index("model"))
                    else:
                        st.dataframe(dfq)
                else:
                    st.dataframe(dfq)
        except Exception as e:
            st.error(str(e))

    st.markdown("---")
    # Custom SQL editor (collapsible) — keep open option and persist SQL text
    keep_open = True

    # persist the custom SQL text across reruns
    if "custom_sql_text" not in st.session_state:
        st.session_state["custom_sql_text"] = "SELECT * FROM telemetry_events LIMIT 50"

    expanded_state = True if keep_open else False
    with st.expander("Custom SQL (run any query)", expanded=expanded_state):
        # initialize session state above;
        # pass the key only to avoid creating the widget with a default
        # value while also setting it via the Session State API
        # (which triggers a Streamlit warning).
        custom_sql = st.text_area("SQL", height=200, key="custom_sql_text")
        if st.button("Run custom SQL"):
            # Safety checks: only allow read-only SELECT queries and block dangerous keywords
            def is_safe_sql(sql_text: str) -> tuple[bool, str]:
                sql_clean = sql_text.strip()
                if not sql_clean:
                    return False, "Empty query"
                # disallow multiple statements
                if (
                    ";" in sql_clean
                    and not sql_clean.rstrip().endswith(";")
                    and sql_clean.count(";") > 0
                ):
                    return (
                        False,
                        "Multiple statements detected; only single SELECT allowed",
                    )
                # require query to start with SELECT (allow whitespace/comments before)
                if not re.match(
                    r"^\s*(/\*.*?\*/\s*)*(--.*?\n\s*)*SELECT\b",
                    sql_clean,
                    flags=re.I | re.S,
                ):
                    return False, "Only single SELECT queries are allowed for security"
                # block dangerous keywords anywhere as whole words
                forbidden = r"\b(" + "|".join(DANGEROUS_SQL_KEYWORDS) + r")\b"
                if re.search(forbidden, sql_clean, flags=re.I):
                    return False, "Query contains forbidden operations"
                return True, ""

            safe, reason = is_safe_sql(custom_sql)
            if not safe:
                st.error(f"Unsafe query blocked: {reason}")
            else:
                # run query against a temporary copy of the DB to avoid any accidental mutations
                tmp_dir = tempfile.mkdtemp(prefix="analytics-db-")
                tmp_db = os.path.join(tmp_dir, "analytics_copy.db")
                try:
                    shutil.copy(get_db_path(), tmp_db)
                    with duckdb.connect(tmp_db) as c:
                        res_custom = c.execute(custom_sql).fetchdf()
                    if res_custom.empty:
                        st.info("Query returned no rows")
                    else:
                        st.dataframe(res_custom)
                except Exception as e:
                    st.error(f"SQL error: {e}")
                finally:
                    # clean up temp copy
                    try:
                        os.remove(tmp_db)
                        os.rmdir(tmp_dir)
                    except Exception:
                        pass


if __name__ == "__main__":
    main()
