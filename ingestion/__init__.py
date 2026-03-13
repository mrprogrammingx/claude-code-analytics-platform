"""Ingestion package.

Contains the ingestion pipeline for parsing telemetry logs and loading
them into the analytics database.
"""
"""ingestion package initializer.

Expose parse_logs at package level for ease of imports in tests.
"""

from . import parse_logs

__all__ = ["parse_logs"]
