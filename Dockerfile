# ─────────────────────────────────────────────────────────────
# DockView — Dockerfile
# ─────────────────────────────────────────────────────────────

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="DockView"
LABEL org.opencontainers.image.version="1.0.0"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 dockview

# Fix docker socket access
RUN groupadd -g 999 docker || true
RUN usermod -aG docker dockview

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=dockview:dockview app/ ./app/

USER dockview

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]