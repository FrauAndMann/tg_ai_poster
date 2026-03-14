# TG AI Poster Dockerfile
# =======================
# Multi-stage build for optimized production image

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ============================================
# Stage 2: Production
# ============================================
FROM python:3.11-slim as production

# Labels
LABEL maintainer="TG AI Poster" \
      version="1.0.0" \
      description="Autonomous AI-powered Telegram posting system"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Disable Python output buffering
    PYTHONFAULTHANDLER=1

# Create non-root user for security
RUN groupadd -r appgroup && \
    useradd -r -g appgroup -d /app -s /sbin/nologin -c "App user" appuser

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    # For Telethon session storage
    sqlite3 \
    # Health check support
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directories
WORKDIR /app
RUN mkdir -p /app/data /app/logs /app/sessions && \
    chown -R appuser:appgroup /app

# Copy application code
COPY --chown=appuser:appgroup . .

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose port for health check endpoint
EXPOSE 8080

# Default command
CMD ["python", "main.py"]

# ============================================
# Stage 3: Development (optional)
# ============================================
FROM production as development

USER root

# Install development tools
RUN pip install --no-cache-dir \
    mypy \
    pytest \
    pytest-asyncio \
    black \
    ruff

USER appuser

# Development command with auto-reload
CMD ["python", "-m", "watchfiles", "main.py"]
