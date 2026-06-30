"""
Talentick — Organizations Router
===================================
دو سطح دسترسی:

1) مدیریت کامل پلتفرم (فقط super_admin):
   GET    /api/orgs/          → لیست همه سازمان‌ها
   POST   /api/orgs/          → ساخت سازمان جدید
   GET    /api/orgs/{id}      → جزئیات هر سازمانی
   PATCH  /api/orgs/{id}      → ویرایش هر سازمانی
   DELETE /api/orgs/{id}      → حذف سازمان (عملیات خطرناک — فقط پلتفرم)

2) مدیریت سازمان خود (org_admin):
   GET   /api/orgs/me         → پروفایل سازمان خودش
   PATCH /api/orgs/me         → ویرایش پروفایل سازمان خودش (نه حذف، نه سازمان‌های دیگر)
   manager به این endpoint ها دسترسی ندارد — فقط می‌تواند کاربران را مدیریت کند.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin, SuperAdmin
from app.schemas.organization import OrganizationCreate, OrganizationResponse, OrganizationUpdate
from app.services import org_service

router = APIRouter(
    prefix="/api/orgs",
    tags=["Organizations"]
)


# ─── مدیریت سازمان خودِ کاربر (org_admin) — باید قبل از /{org_id} تعریف شود ──

@router.get("/me", response_model=OrganizationResponse, summary="پروفایل سازمان خودم")
async def get_my_org(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    return org


@router.patch("/me", response_model=OrganizationResponse, summary="ویرایش پروفایل سازمان خودم")
async def update_my_org(
    body: OrganizationUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    # org_admin نباید بتواند سازمان خودش را غیرفعال کند (آن کار super_admin است)
    if current_user.role != "super_admin":
        body = body.model_copy(update={"is_active": None})
    return await org_service.update_organization(db, org, body)


# ─── مدیریت کامل پلتفرم (super_admin) ─────────────────────────────────────────

@router.get("/", response_model=list[OrganizationResponse])
async def list_orgs(
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return await org_service.list_organizations(db)


@router.post("/", response_model=OrganizationResponse, status_code=201)
async def create_org(
    body: OrganizationCreate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    existing = await org_service.get_by_slug(db, body.slug)
    if existing:
        raise HTTPException(status_code=400, detail="این slug قبلاً استفاده شده است")
    return await org_service.create_organization(db, body)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_org(
    org_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    return org


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_org(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    return await org_service.update_organization(db, org, body)


@router.delete("/{org_id}", status_code=204)
async def delete_org(
    org_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="سازمان یافت نشد")
    await org_service.delete_organization(db, org)
