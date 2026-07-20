"""
Talentick — Points (Gamification) Router (Admin)
====================================================
مدیریت مقدار امتیاز هر نوع اتفاق — سراسری، فقط super_admin.

Routes:
  GET    /api/points/rules                  → لیست قوانین امتیاز پیش‌فرض
  PATCH  /api/points/rules/{id}              → ویرایش مقدار/فعال‌بودن یک قانون
  GET    /api/points/group-overrides         → لیست override های گروهی (نقش/واحد)
  POST   /api/points/group-overrides         → افزودن/به‌روزرسانی override گروهی
  DELETE /api/points/group-overrides/{id}    → حذف override گروهی

override اختصاصی هر موجودیت (آزمون/محتوا/آیتم/مرحله/برنامه) از طریق
router خودِ آن موجودیت تنظیم می‌شود (فیلد points_override در payload
ساخت/ویرایش)، نه اینجا. دیدن امتیاز شخصی/تاریخچه از routers/me.py
(GET /api/me/points/*) است.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import SuperAdmin
from app.schemas.points import (
    PointGroupOverrideCreate,
    PointGroupOverrideResponse,
    PointRuleResponse,
    PointRuleUpdate,
)
from app.services import points_service

router = APIRouter(prefix="/api/points", tags=["Gamification"])


@router.get("/rules", response_model=list[PointRuleResponse], summary="لیست قوانین امتیاز")
async def list_rules(
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rules = await points_service.list_rules(db)
    return [points_service.rule_to_response(r) for r in rules]


@router.patch("/rules/{rule_id}", response_model=PointRuleResponse, summary="ویرایش مقدار/فعال‌بودن یک قانون امتیاز")
async def update_rule(
    rule_id: str,
    body: PointRuleUpdate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rule = await points_service.get_rule_by_id(db, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قانون امتیاز یافت نشد")
    updated = await points_service.update_rule(db, rule, body.points, body.is_active)
    return points_service.rule_to_response(updated)


# ─── Group Overrides (نقش/واحد سازمانی) ────────────────────────────────────

@router.get("/group-overrides", response_model=list[PointGroupOverrideResponse], summary="لیست override های گروهی")
async def list_group_overrides(
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
    event_type: str | None = None,
):
    overrides = await points_service.list_group_overrides(db, event_type)
    return [await points_service.group_override_to_response(db, o) for o in overrides]


@router.post(
    "/group-overrides", response_model=PointGroupOverrideResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن (یا به‌روزرسانی) override گروهی برای یک نقش/واحد",
)
async def create_group_override(
    body: PointGroupOverrideCreate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    override = await points_service.create_group_override(
        db, body.event_type, body.target_type, body.target_value, body.points
    )
    return await points_service.group_override_to_response(db, override)


@router.delete("/group-overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف override گروهی")
async def delete_group_override(
    override_id: str,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    override = await points_service.get_group_override(db, override_id)
    if not override:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "override یافت نشد")
    await points_service.delete_group_override(db, override)
