"""
Talentick — Positions Router
===============================
پست‌های سازمانی — CRUD کامل با Org Isolation (manager به بالا).

Routes:
  GET    /api/positions/?dept_id=...  → لیست پست‌ها (با فیلتر اختیاری واحد)
  POST   /api/positions/              → ساخت پست جدید
  GET    /api/positions/template      → دانلود قالب نمونه Import (Excel)
  GET    /api/positions/export        → خروجی Excel از پست‌های سازمان
  POST   /api/positions/import        → Import گروهی از Excel (تطبیق بر اساس نام)
  GET    /api/positions/{id}          → جزئیات
  PATCH  /api/positions/{id}          → ویرایش
  DELETE /api/positions/{id}          → حذف
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.dependencies import Manager
from app.dependencies import enforce_org_scope as _enforce_org_scope
from app.models.organization import Position
from app.models.user import User
from app.schemas.position import PositionCreate, PositionImportResult, PositionResponse, PositionUpdate
from app.services import department_service, position_excel_service, position_service

router = APIRouter(prefix="/api/positions", tags=["Positions"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID:
    """
    تعیین org_id مرجع برای GET لیستی.
    super_admin می‌تواند org_id دلخواه بدهد (برای مدیریت سازمان دیگران)،
    سایر نقش‌ها همیشه محدود به سازمان خودشان هستند.
    """
    if current_user.role == "super_admin" and org_id:
        try:
            return uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


@router.get(
    "/", response_model=list[PositionResponse], summary="لیست پست‌های سازمان",
    description="لیست پست‌های سازمانی — با `dept_id` می‌توان فقط پست‌های یک دپارتمان را گرفت. **دسترسی:** manager به بالا.",
)
async def list_positions(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    dept_id: str | None = Query(None, description="فیلتر بر اساس واحد"),
    org_id: str | None = Query(None, description="فقط super_admin — مدیریت سازمان دلخواه"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    return await position_service.list_positions(db, target_org_id, dept_id=dept_id)


@router.post(
    "/", response_model=PositionResponse, status_code=status.HTTP_201_CREATED, summary="ساخت پست جدید",
    description="ساخت پست سازمانی جدید — `level` بین ۱ (کارمند) تا ۸ (مدیرعامل). **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={400: {"description": "واحد سازمانی (dept_id) معتبر نیست"}},
)
async def create_position(
    body: PositionCreate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    org_id = current_user.org_id
    if current_user.role == "super_admin" and body.org_id:
        org_id = uuid.UUID(body.org_id)

    if body.dept_id:
        dept = await department_service.get_department(db, body.dept_id)
        if not dept or str(dept.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد سازمانی معتبر نیست")

    pos = await position_service.create_position(db, org_id, body)
    return await position_service.to_response(db, pos)


# ─── Excel: قالب / خروجی / Import ─────────────────────────────────────────────

@router.get(
    "/template",
    summary="دانلود قالب نمونه Import پست‌های سازمانی (Excel)",
    description="فایل Excel نمونه شامل ستون‌های موردنیاز، یک ردیف داده نمونه و شیت راهنما.",
)
async def download_position_import_template(
    current_user: Manager,
) -> StreamingResponse:
    content = position_excel_service.build_template_workbook()
    return StreamingResponse(
        iter([content]),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=talentick-positions-template.xlsx"},
    )


@router.get(
    "/export",
    summary="خروجی Excel از پست‌های سازمانی",
    description="خروجی بر اساس فیلتر اختیاری `dept_id`. **دسترسی:** manager به بالا (سازمان خودشان؛ super_admin با `org_id`).",
)
async def export_positions_excel(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    dept_id: str | None = Query(None, description="فیلتر بر اساس واحد"),
    org_id: str | None = Query(None, description="فقط super_admin — مدیریت سازمان دلخواه"),
) -> StreamingResponse:
    target_org_id = _resolve_org_id(current_user, org_id)

    q = select(Position).where(Position.org_id == target_org_id).options(joinedload(Position.department))
    if dept_id:
        q = q.where(Position.dept_id == uuid.UUID(dept_id))
    result = await db.execute(q.order_by(Position.level.desc(), Position.created_at))
    positions = list(result.scalars().all())

    content = await position_excel_service.build_export_workbook(db, positions)
    return StreamingResponse(
        iter([content]),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": "attachment; filename=talentick-positions-export.xlsx"},
    )


@router.post(
    "/import",
    response_model=PositionImportResult,
    summary="Import گروهی پست‌های سازمانی از Excel",
    description="""
    **دسترسی:** manager به بالا.

    - manager/org_admin: همیشه در سازمان خودش import می‌کند.
    - super_admin: باید org_id را در query مشخص کند.
    - تطبیق بر اساس «عنوان پست» است — پستی با نام تکراری (در همان سازمان) به‌روزرسانی می‌شود.
    """,
)
async def import_positions_excel(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    org_id: str | None = Query(None, description="الزامی فقط برای super_admin"),
) -> PositionImportResult:
    target_org_id = _resolve_org_id(current_user, org_id)

    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط فایل Excel (.xlsx) پذیرفته می‌شود")

    data = await file.read()
    return await position_excel_service.import_positions_from_excel(db, target_org_id, data)


@router.get(
    "/{position_id}", response_model=PositionResponse, summary="جزئیات پست",
    description="جزئیات یک پست سازمانی. **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={403: {"description": "دسترسی به این سازمان مجاز نیست"}, 404: {"description": "پست یافت نشد"}},
)
async def get_position(
    position_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    pos = await position_service.get_position(db, position_id)
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پست یافت نشد")
    _enforce_org_scope(current_user, pos.org_id)
    return await position_service.to_response(db, pos)


@router.patch(
    "/{position_id}", response_model=PositionResponse, summary="ویرایش پست",
    description="ویرایش partial یک پست سازمانی. **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={
        400: {"description": "واحد سازمانی معتبر نیست"},
        403: {"description": "دسترسی به این سازمان مجاز نیست"},
        404: {"description": "پست یافت نشد"},
    },
)
async def update_position(
    position_id: str,
    body: PositionUpdate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    pos = await position_service.get_position(db, position_id)
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پست یافت نشد")
    _enforce_org_scope(current_user, pos.org_id)

    if body.dept_id:
        dept = await department_service.get_department(db, body.dept_id)
        if not dept or str(dept.org_id) != str(pos.org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد سازمانی معتبر نیست")

    updated = await position_service.update_position(db, pos, body)
    return await position_service.to_response(db, updated)


@router.delete(
    "/{position_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف پست",
    description="حذف پست سازمانی. **دسترسی:** manager به بالا (سازمان خودشان).",
    responses={403: {"description": "دسترسی به این سازمان مجاز نیست"}, 404: {"description": "پست یافت نشد"}},
)
async def delete_position(
    position_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    pos = await position_service.get_position(db, position_id)
    if not pos:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پست یافت نشد")
    _enforce_org_scope(current_user, pos.org_id)
    await position_service.delete_position(db, pos)