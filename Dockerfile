# Multi-stage Dockerfile for hn.fm backend
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock README.md LICENSE ./

# Install uv and create virtual environment, then install dependencies
RUN pip install uv && \
    uv venv && \
    . .venv/bin/activate && \
    uv pip install -e . && \
    uv pip install --group dev

# Copy source code and scripts
COPY src/ ./src/
COPY config.yaml ./

# Change ownership to app user
RUN chown -R app:app /app
USER app

# Set PATH to include virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Default command
CMD ["python", "src/hnfm/scripts/run_web_server.py"]
