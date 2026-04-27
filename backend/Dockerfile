FROM python:3.11-slim AS base

WORKDIR /app

# Dependencias del sistema — mínimas para Sprint 0
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Stub mínimo para que hatchling pueda generar metadata antes de copiar el código.
# El COPY . . posterior sobrescribe con el código real.
RUN mkdir -p app && touch app/__init__.py

# Instala el extra "demo" — agrega sentence-transformers (embeddings RAG) y
# faster-whisper (transcripción). El primer build descarga PyTorch CPU
# (~700 MB) + ctranslate2 (~300 MB). Builds posteriores usan caché Docker.
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[demo]"

# ── Development ───────────────────────────────────────────────────────────────
FROM base AS development
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────────────────────────────
FROM base AS production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
