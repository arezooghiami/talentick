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

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import auth, content, dashboard, departments, organizations, positions, users


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup و Shutdown hooks.

    Startup: بررسی اتصال دیتابیس
    """
    # در آینده: health check اتصال DB و MinIO
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routers ──────────────────────────────────────────────────────────────
# ترتیب مهم نیست اما گروه‌بندی منطقی نگه می‌داریم

app.include_router(auth.router)           # POST /api/auth/login, GET /api/auth/me
app.include_router(organizations.router)  # CRUD /api/orgs
app.include_router(users.router)          # CRUD /api/users
app.include_router(departments.router)    # CRUD /api/departments
app.include_router(positions.router)      # CRUD /api/positions
app.include_router(content.router)        # CRUD /api/contents
app.include_router(dashboard.router)      # GET /api/dashboard/super-admin

# ─── Static Frontend ──────────────────────────────────────────────────────────
# frontend/ دایرکتوری مجاور backend/ است
# باید بعد از router ها mount بشه تا /api/* اول match بشه
from pathlib import Path

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/login.html")

# ─── Static frontend — باید آخر از همه باشه ──────────────────────────────────
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")