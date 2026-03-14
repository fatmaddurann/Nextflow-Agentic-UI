# =====================================================
# Nextflow-Agentic-UI — Backend Dockerfile
# Multi-stage build for a lean production image
# =====================================================

# Stage 1: Dependency builder
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# Stage 2: Production image
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="Nextflow-Agentic-UI" \
      description="FastAPI backend for bioinformatics pipeline management"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
        ca-certificates \
        # For Docker SDK
        docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Java (required for Nextflow)
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Nextflow
RUN curl -s https://get.nextflow.io | bash \
    && mv nextflow /usr/local/bin/ \
    && chmod +x /usr/local/bin/nextflow \
    && nextflow info || true

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r nfagent && useradd -r -g nfagent -d /app nfagent \
    && usermod -aG docker nfagent 2>/dev/null || true

WORKDIR /app

# Copy application code
COPY --chown=nfagent:nfagent . .

# Create required directories
RUN mkdir -p data /pipeline/work /pipeline/results /pipeline/logs /tmp/nf_uploads \
    && chown -R nfagent:nfagent /app /pipeline /tmp/nf_uploads

USER nfagent

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
