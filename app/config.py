# project_root/config.py

import os
from pathlib import Path

API_TITLE = "Claude Telemetry Analytics API"
API_VERSION = "1.0.0"
# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "analytics.db"))

# Data directories
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data_generator" / "output"))

# Data files
LOG_PATH = DATA_DIR / "telemetry_logs.jsonl"
EMPLOYEE_PATH = DATA_DIR / "employees.csv"

# Ensure the data directory exists when the config is loaded. This makes it
# convenient for scripts that rely on the path being present (tests or demos).
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # Best-effort: if the directory cannot be created (permissions etc.),
    # leave it to the caller to handle. We don't raise here to keep imports safe.
    pass

# Realtime simulator / stream file
REALTIME_STREAM_FILE = DATA_DIR / "realtime_stream.jsonl"

DEFAULT_EVENT_LIMIT = 100

CHUNK_SIZE = 10_000_000  # adjust based on memory

TABLE_NAMES = {"telemetry": "telemetry_events", "employees": "employees"}

DANGEROUS_SQL_KEYWORDS = [
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "truncate",
    "attach",
    "detach",
    "pragma",
    "copy",
    "vacuum",
    "shutdown",
]

# Models directory & persistence
# Allow overriding via env var (useful in CI or tests)
MODELS_DIR = Path(os.getenv("MODELS_DIR", BASE_DIR / "models"))
try:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    # best-effort; callers can create the dir if necessary
    pass

MODEL_PATH = MODELS_DIR / "forecast.joblib"

# Mapping used by trainer and API for demo model categories. Keep here so the
# trainer and API stay consistent.
MODEL_CODE_MAP = {"claude-v1": 0, "claude-instant": 1, "gpt-4": 2}
