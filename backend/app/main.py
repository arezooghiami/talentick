"""
Talentick — FastAPI Application Entry Point
=============================================
یک uvicorn instance هم backend API هم frontend static files رو serve می‌کنه.

آدرس‌ها:
- /api/*         → FastAPI routers
- /*             → Static frontend files (frontend/ directory)

راه‌اندازی:
    uvicorn app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.core.storage import ensure_bucket
from app.database import engine
from app.routers import announcements, auth, content, dashboard, departments, documents, me, onboarding, organizations, positions, quizzes, reports, tickets, users

logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup و Shutdown hooks.

    Startup: اطمینان از وجود bucket و اعمال سیاست public-read روی آن —
    بدون این کار، فایل‌های آپلودشده (کاور/PDF/ویدیو و ...) با خطای
    Access Denied مواجه می‌شوند چون MinIO به‌صورت پیش‌فرض bucket را
    private می‌سازد.
    """
    try:
        ensure_bucket()
    except Exception:
        logger.warning("اتصال به MinIO در زمان راه‌اندازی برقرار نشد — bucket در اولین آپلود بررسی می‌شود.")
    yield


# ─── App Instance ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Talentick API",
    description="پلتفرم یادگیری و آنبوردینگ سازمانی",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
# ⚠️ نکته امنیتی مهم: origin=["*"] به‌همراه allow_credentials=True طبق
# مشخصات CORS نامعتبر است (مرورگرها آن را رد می‌کنند) و در صورت کارکرد
# هم یعنی هر وب‌سایتی می‌تواند با اعتبار (کوکی/Authorization) کاربر
# درخواست بزند — ریسک امنیتی جدی. به‌همین دلیل از allowed_origins در
# .env استفاده می‌شود؛ در Production باید فقط دامنه(های) واقعی فرانت
# در ALLOWED_ORIGINS باشد.
logger.info("CORS allowed_origins=%s", settings.allowed_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Security Headers ─────────────────────────────────────────────────────────
# هدرهای پایه‌ای امنیتی که در پاسخ API هم (نه فقط استاتیک فرانت پشت Nginx)
# باید حاضر باشند — چون در dev/بدون Nginx هم uvicorn مستقیم پاسخ می‌دهد.
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# ─── Health Check ─────────────────────────────────────────────────────────────
# مسیر خارج از پیشوند /api عمداً انتخاب شده تا با HEALTHCHECK در Dockerfile
# (curl http://localhost:8000/health) و nginx.conf هم‌راستا باشد.
@app.get("/health", include_in_schema=False)
async def health_check() -> JSONResponse:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed — database unreachable")
        return JSONResponse(status_code=503, content={"status": "unhealthy"})
    return JSONResponse(status_code=200, content={"status": "ok"})

# ─── API Routers ──────────────────────────────────────────────────────────────
# ترتیب مهم نیست اما گروه‌بندی منطقی نگه می‌داریم

app.include_router(auth.router)           # POST /api/auth/login, GET /api/auth/me
app.include_router(organizations.router)  # CRUD /api/orgs
app.include_router(users.router)          # CRUD /api/users
app.include_router(departments.router)    # CRUD /api/departments
app.include_router(positions.router)      # CRUD /api/positions
app.include_router(content.router)        # CRUD /api/contents
app.include_router(documents.router)      # CRUD /api/documents — کتابخانه اسناد
app.include_router(quizzes.router)        # CRUD /api/quizzes + گزارش تلاش‌ها
app.include_router(dashboard.router)      # GET /api/dashboard/super-admin
app.include_router(me.router)             # GET /api/me/contents, /api/me/quizzes — پرتال کاربر (LMS)
app.include_router(reports.router)        # GET /api/reports/* — BI و گزارش‌گیری
app.include_router(announcements.router)  # CRUD /api/announcements — مدیریت اطلاعیه‌ها
app.include_router(onboarding.router)     # CRUD /api/onboarding — برنامه‌های آشنایی سازمانی
app.include_router(tickets.router)        # CRUD /api/tickets — تیکتینگ (پشتیبانی/بازخورد)

# ─── Static Frontend ──────────────────────────────────────────────────────────
# frontend/ دایرکتوری مجاور backend/ است
# باید بعد از router ها mount بشه تا /api/* اول match بشه
# StaticFiles(html=True) خودش «/» را به frontend/index.html (صفحه‌ی landing) سرو می‌کند.
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")