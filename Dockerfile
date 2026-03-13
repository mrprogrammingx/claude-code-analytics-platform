FROM python:3.11-slim
WORKDIR /app

# Install system deps (if any) and copy project
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501 8000

# Pre-generate sample data and ingest into analytics.db so the image is demo-ready.
RUN mkdir -p data_generator/output && \
    cd data_generator && \
    python generate_fake_data.py --num-users 50 --num-sessions 500 --days 30 && \
    cd .. && \
    python -m ingestion.parse_logs --log-path data_generator/output/telemetry_logs.jsonl --employee-path data_generator/output/employees.csv --db-path analytics.db --chunk-size 500 || true

# Default: start Streamlit dashboard
CMD ["python", "-m", "streamlit", "run", "dashboard/main.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
