# ─────────────────────────────────────────────────────────────
# DockView — Dockerfile
# Multi-stage, minimal, production-grade
# ─────────────────────────────────────────────────────────────

# ── Stage 1: dependency builder ──────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="DockView"
LABEL org.opencontainers.image.description="Zero-config Docker database viewer"
LABEL org.opencontainers.image.version="1.0.0"

# Runtime deps for psycopg2 / asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 dockview

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application
COPY --chown=dockview:dockview app/ ./app/

# Switch to non-root
USER dockview

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
