"""Ingestion package.

Contains the ingestion pipeline for parsing telemetry logs and loading
them into the analytics database. We expose ``parse_logs`` at package level
for convenience (tests and simple imports).
"""

from . import parse_logs  # re-export for convenience

__all__ = ["parse_logs"]
