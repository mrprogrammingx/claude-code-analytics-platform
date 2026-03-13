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

# Default: start Streamlit dashboard
CMD ["python", "-m", "streamlit", "run", "dashboard/main.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
