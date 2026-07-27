# =============================================================================
# Talentick Backend — Dockerfile
# Python 3.12 slim — multi-stage با Poetry، بدون virtualenv اضافه در ایمیج نهایی
# =============================================================================
# ⚠️ Build context این Dockerfile باید ریشه‌ی مونوریپو باشد (نه backend/)
# چون pyproject.toml/poetry.lock آنجا هستند:
#   docker build -f backend/Dockerfile .
# در docker-compose.yml/docker-compose.prod.yml معادل آن:
#   build: { context: ., dockerfile: backend/Dockerfile }

# ─── Stage 1: Builder — نصب وابستگی‌ها با Poetry ───────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry>=2.0.0,<3.0.0"

WORKDIR /build

# فقط فایل‌های قفل وابستگی کپی می‌شوند تا cache layer با تغییر کد نشکند
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# ─── Stage 2: Runtime — فقط venv نصب‌شده + سورس کپی می‌شود ──────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/build/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/.venv /build/.venv
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY backend/seed.py ./seed.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# ─── در docker-compose.yml command را override می‌کنیم ─────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
