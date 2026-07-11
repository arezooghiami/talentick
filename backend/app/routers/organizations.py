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

router = APIRouter(prefix="/api/orgs", tags=["Organizations"])

_NOT_FOUND_RESPONSES = {404: {"description": "سازمان یافت نشد"}}


# ─── مدیریت سازمان خودِ کاربر (org_admin) — باید قبل از /{org_id} تعریف شود ──

@router.get(
    "/me",
    response_model=OrganizationResponse,
    summary="پروفایل سازمان خودم",
    description="پروفایل کامل سازمانِ کاربر لاگین‌شده. **دسترسی:** org_admin و super_admin.",
    responses=_NOT_FOUND_RESPONSES,
)
async def get_my_org(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = await org_service.get_organization(db, current_user.org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سازمان یافت نشد")
    return org


@router.patch(
    "/me",
    response_model=OrganizationResponse,
    summary="ویرایش پروفایل سازمان خودم",
    description="""
    ویرایش partial پروفایل سازمانِ کاربر لاگین‌شده (نام، توضیحات،
    مأموریت/چشم‌انداز/ارزش‌ها/فرهنگ، اطلاعات تماس و ...).

    **دسترسی:** org_admin و super_admin.

    **نکته:** فیلد `is_active` حتی اگر در بدنه ارسال شود، برای org_admin
    نادیده گرفته می‌شود — غیرفعال‌سازی کل سازمان فقط در اختیار
    super_admin است (از طریق `PATCH /api/orgs/{org_id}`).
    """,
    responses=_NOT_FOUND_RESPONSES,
)
async def update_my_org(
    body: OrganizationUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = await org_service.get_organization(db, current_user.org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سازمان یافت نشد")
    # org_admin نباید بتواند سازمان خودش را غیرفعال کند (آن کار super_admin است)
    if current_user.role != "super_admin":
        body = body.model_copy(update={"is_active": None})
    return await org_service.update_organization(db, org, body)


# ─── مدیریت کامل پلتفرم (super_admin) ─────────────────────────────────────────

@router.get(
    "/",
    response_model=list[OrganizationResponse],
    summary="لیست همه سازمان‌ها",
    description="لیست کامل تمام سازمان‌های (tenant) پلتفرم — مرتب‌شده بر اساس تاریخ ساخت (جدیدترین اول). **دسترسی:** فقط super_admin.",
)
async def list_orgs(
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
) -> list[OrganizationResponse]:
    return await org_service.list_organizations(db)


@router.post(
    "/",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="ساخت سازمان جدید",
    description="ایجاد یک tenant جدید روی پلتفرم. **دسترسی:** فقط super_admin. `slug` باید در کل پلتفرم یکتا باشد.",
    responses={400: {"description": "slug تکراری است"}},
)
async def create_org(
    body: OrganizationCreate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    existing = await org_service.get_by_slug(db, body.slug)
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این slug قبلاً استفاده شده است")
    return await org_service.create_organization(db, body)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="جزئیات یک سازمان",
    description="جزئیات کامل هر سازمانی با شناسه‌ی آن. **دسترسی:** فقط super_admin.",
    responses=_NOT_FOUND_RESPONSES,
)
async def get_org(
    org_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سازمان یافت نشد")
    return org


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="ویرایش هر سازمانی",
    description="ویرایش partial هر سازمانی — از جمله فعال/غیرفعال‌سازی کامل (`is_active`). **دسترسی:** فقط super_admin.",
    responses=_NOT_FOUND_RESPONSES,
)
async def update_org(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سازمان یافت نشد")
    return await org_service.update_organization(db, org, body)


@router.delete(
    "/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="حذف سازمان (خطرناک)",
    description="""
    **⚠️ عملیات مخرب و غیرقابل بازگشت.** به‌دلیل `ondelete=CASCADE`
    روی کلیدهای خارجی، حذف یک سازمان تمام کاربران، دپارتمان‌ها،
    پست‌ها، محتوا و داده‌های وابسته‌ی آن سازمان را نیز حذف می‌کند.

    **دسترسی:** فقط super_admin. توصیه می‌شود در فرانت یک تأییدیه‌ی
    دو مرحله‌ای (مثلاً تایپ نام سازمان) قبل از صدا زدن این endpoint
    نمایش داده شود.
    """,
    responses=_NOT_FOUND_RESPONSES,
)
async def delete_org(
    org_id: uuid.UUID,
    _: SuperAdmin,
    db: AsyncSession = Depends(get_db),
) -> None:
    org = await org_service.get_organization(db, org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سازمان یافت نشد")
    await org_service.delete_organization(db, org)
