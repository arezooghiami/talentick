# =============================================================================
# Talentick Backend — Dockerfile
# Python 3.12 slim — multi-stage، venv دستی + pip (بدون Poetry داخل ایمیج)
# =============================================================================
# ⚠️ Build context این Dockerfile باید ریشه‌ی مونوریپو باشد چون
# backend/requirements.txt آنجاست:
#   docker build -f backend/Dockerfile .
# در docker-compose.yml/docker-compose.prod.yml معادل آن:
#   build: { context: ., dockerfile: backend/Dockerfile }
#
# ⚠️ backend/requirements.txt از poetry.lock تولید می‌شود — منبع حقیقتِ
# نسخه‌ها همچنان pyproject.toml/poetry.lock است. با هر تغییر وابستگی‌ها،
# این فایل باید دوباره export شود:
#   poetry export --format requirements.txt --without-hashes -o backend/requirements.txt

# ─── Stage 1: Builder — نصب وابستگی‌ها با pip در یک venv مجزا ──────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_RETRIES=10

# apt-get عمداً حذف شده: psycopg[binary]/psycopg2-binary در pyproject.toml
# wheel از پیش‌کامپایل‌شده با libpq استاتیک دارند — نیازی به gcc/libpq-dev
# برای build نیست.
#
# Poetry هم عمداً داخل ایمیج نصب نمی‌شود: خودِ Poetry حدود ۳۰ پکیج
# جانبی (cleo, cachecontrol, build, keyring, ...) دارد که ربطی به اپ
# ندارند و روی شبکه‌ی کند سرور، همین نصب اولیه‌ی Poetry (نه پکیج‌های
# واقعی اپ) تنها‌ترین گلوگاه بود. به‌جایش از backend/requirements.txt
# (خروجی poetry export) مستقیم با pip نصب می‌کنیم.
WORKDIR /build

COPY backend/requirements.txt ./
RUN python -m venv .venv \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

# ─── Stage 2: Runtime — فقط venv نصب‌شده + سورس کپی می‌شود ──────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/build/.venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /build/.venv /build/.venv
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY backend/seed.py ./seed.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

EXPOSE 8000

# ─── در docker-compose.yml command را override می‌کنیم ─────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
