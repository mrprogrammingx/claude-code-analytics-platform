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

DEFAULT_EVENT_LIMIT = 100

CHUNK_SIZE = 10_000_000  # adjust based on memory

TABLE_NAMES = {
    "telemetry": "telemetry_events",
    "employees": "employees"
}

DANGEROUS_SQL_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "pragma", "copy",
    "vacuum", "shutdown"
]