# Game Localization MVR - Docker Image
# Multi-stage build for smaller final image

FROM python:3.11-slim AS base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY workflow/ ./workflow/
COPY glossary/ ./glossary/
COPY docs/ ./docs/

# Create data directory (will be mounted as volume in production)
RUN mkdir -p /app/data

# Default environment variables (override at runtime)
ENV LLM_TRACE_PATH=/app/data/llm_trace.jsonl

# Health check - verify Python and key dependencies
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import yaml; import requests; print('OK')" || exit 1

# Default command: show help
CMD ["python", "scripts/llm_ping.py"]
