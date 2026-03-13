 (See LLM_USAGE_LOG.md for the original detailed prompt log.)

## LLM Usage (summary)

This project used Claude, Copilot and ChatGPT for architecture sketches, helper code, and documentation.

See `LLM_USAGE_LOG.md` for the detailed log of prompts and outputs.
# LLM Usage

This project followed an AI-first workflow to accelerate development. The notes below summarize which LLMs were used, why they were used, sample prompts, and how the outputs were validated.

## Tools used
- Claude / Claude Code: used for architecture brainstorming, sanitization guidance, and iterative code generation for ingestion and API helpers.
- GitHub Copilot: used as an inline assistant while writing code (minor boilerplate and test scaffolding).
- ChatGPT (OpenAI): used for example prompts, SQL shaping, and editing larger documentation passages.

## Why use LLMs
- Speed: prototype code and SQL quickly and iterate on corner cases.
- Style and consistency: generate consistent docstrings, unit tests, and README content.
- Edge-case handling: generate sanitizers and JSON serialization guidance for complex types.

## Sample prompts (6–10)
Below are representative prompts used during the project and short notes on the expected output.

1. Ingest parser
  - Prompt: "Write a Python function that reads a JSONL of logs with nested 'message' strings, normalizes dotted attribute keys into underscored columns, coerces numeric fields and converts timestamp (ms) to pandas datetime, returning a DataFrame ready for DuckDB ingestion." 
  - Expected: A `process_chunk` function that flattens nested fields, handles JSON parsing errors, and computes `ts` and `total_tokens`.

2. Sanitizer for API responses
  - Prompt: "Provide a robust sanitizer function that converts Pandas/NumPy scalars and timestamps to JSON-serializable Python types, replacing infinities/NaNs with nulls." 
  - Expected: A recursive sanitizer that handles numpy scalars, pandas.Timestamp, Decimal, and nested dict/list structures.

3. SQL design for analytics
  - Prompt: "Write DuckDB SQL to compute total tokens by user role and hourly event counts for a telemetry_events table with columns (user_email, total_tokens, ts)." 
  - Expected: Aggregations using GROUP BY with COALESCE, DATE_TRUNC/EXTRACT on `ts`, and joins against `employees` table.

4. Streamlit dashboard layout
  - Prompt: "Create a Streamlit app skeleton that shows top-level metrics, a time-series chart, a table of top users, and a safe SQL editor with a preview limit." 
  - Expected: `st.columns` metrics, `st.line_chart` for time-series, and a `st.text_area` + preview button for custom queries.

5. Unit test scaffolding
  - Prompt: "Write pytest tests for the ingestion helper functions: safe_int, safe_float, and process_chunk minimal smoke-test." 
  - Expected: Tests that exercise conversions and an example minimal event JSONL record.

6. CI / pre-commit config guidance
  - Prompt: "Provide a GitHub Actions workflow that installs Python, installs runtime and dev dependencies, runs pre-commit, lints, and pytest." 
  - Expected: A matrix workflow for multiple Python versions, with steps for installing dev deps and running pre-commit and pytest.

## Validation steps for each prompt
- Ingest parser: Unit tests (see `tests/test_ingest_helpers.py`) verify `process_chunk` behavior; integration test `tests/test_api.py` verifies end-to-end ingest → API flows on a small sample.
- Sanitizer: exercised via API integration tests which call `/telemetry` and ensure responses are JSON-serializable; manual spot checks were performed with DuckDB outputs.
- SQL design: run directly against the sample `analytics.db` with DuckDB shell and via the Streamlit dashboard to validate aggregates and edge cases.
- Streamlit layout: manual verification by running the dashboard locally and visually confirming charts and metrics render correctly with sample data.
- Unit tests: executed locally and in CI (pytest), tests are quick and deterministic.
- CI / pre-commit: run locally in a virtualenv and verified in GitHub Actions; pre-commit hooks were adjusted to use system-installed tools to avoid network fetch issues in some local environments.

## Notes and best practices
- Keep prompts focused and iterative — ask for the smallest useful unit (one function or one SQL query) then iterate.
- Always add unit tests for AI-generated logic and validate against small, deterministic inputs.
- Capture prompt engineering decisions and store them in `docs/LLM_USAGE.md` so reviewers understand which parts were AI-assisted.
