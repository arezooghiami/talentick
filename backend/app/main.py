"""
Talentick — FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # ← اضافه
from fastapi.responses import RedirectResponse  # ← اضافه

from app.config import settings
from app.routers import auth, organizations, users

app = FastAPI(
    title="Talentick API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routers ──────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(organizations.router, prefix="/api/orgs", tags=["Organizations"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "app": settings.app_name}

# ─── Redirect / به login ──────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/login.html")

# ─── Static frontend — باید آخر از همه باشه ──────────────────────────────────
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend") 