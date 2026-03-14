# =====================================================
# Nextflow-Agentic-UI — Log Monitor Sidecar
# =====================================================
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir httpx aiofiles structlog python-dotenv

COPY monitor.py .

CMD ["python", "-u", "monitor.py"]
