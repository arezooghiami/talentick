"""
Talentick — Points (Gamification) Router (Admin)
====================================================
مدیریت موتور امتیازدهی — بخش‌های اول تا چهارم اسپک. فقط super_admin
سیاست‌گذاری می‌کند (Ruleها/Policy Ruleها)؛ تراکنش دستی و مشاهده‌ی
دفترکل سازمان برای org_admin (سازمان خودش) هم باز است.

Routes:
  GET    /api/points/rules                     → لیست انواع Event و مقدار پیش‌فرض هرکدام
  POST   /api/points/rules                      → تعریف نوع Event جدید (Event Driven)
  PATCH  /api/points/rules/{id}                  → ویرایش مقدار/برچسب/فعال‌بودن یک Event
  GET    /api/points/policy-rules                → لیست استثناهای Priority Engine (User/Position/Department/Organization)
  POST   /api/points/policy-rules                → افزودن استثنا
  PATCH  /api/points/policy-rules/{id}            → ویرایش استثنا
  DELETE /api/points/policy-rules/{id}            → حذف استثنا
  POST   /api/points/manual-transactions          → تراکنش دستی (bonus/manual_adjustment/deduction/correction)
  GET    /api/points/ledger                       → دفترکل سازمان (org_admin: سازمان خودش — super_admin: با فیلتر org_id)

override اختصاصی هر موجودیت (آزمون/محتوا/آیتم/مرحله/برنامه) از طریق
router خودِ آن موجودیت تنظیم می‌شود (فیلد points_override در payload
ساخت/ویرایش)، نه اینجا. دیدن امتیاز شخصی/تاریخچه از routers/me.py است.
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin, SuperAdmin, enforce_org_scope
from app.schemas.points import (
    ManualTransactionCreate,
    PointPolicyRuleCreate,
    PointPolicyRuleResponse,
    PointPolicyRuleUpdate,
    PointRuleCreate,
    PointRuleResponse,
    PointRuleUpdate,
    PointsHistoryResponse,
    PointsLedgerEntryResponse,
)
from app.services import points_service

router = APIRouter(prefix="/api/points", tags=["Gamification"])


# ─── Event Rules (سراسری — Event Driven) ───────────────────────────────────

@router.get("/rules", response_model=list[PointRuleResponse], summary="لیست انواع Event و مقدار پیش‌فرض هرکدام")
async def list_rules(
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rules = await points_service.list_rules(db)
    return [points_service.rule_to_response(r) for r in rules]


@router.post(
    "/rules", response_model=PointRuleResponse, status_code=status.HTTP_201_CREATED,
    summary="تعریف نوع Event جدید (Event Driven — بدون نیاز به تغییر کد)",
)
async def create_rule(
    body: PointRuleCreate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    return points_service.rule_to_response(await points_service.create_rule(db, body, current_user.id))


@router.patch("/rules/{rule_id}", response_model=PointRuleResponse, summary="ویرایش مقدار/برچسب/فعال‌بودن یک Event")
async def update_rule(
    rule_id: str,
    body: PointRuleUpdate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rule = await points_service.get_rule_by_id(db, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قانون امتیاز یافت نشد")
    updated = await points_service.update_rule(db, rule, body, current_user.id)
    return points_service.rule_to_response(updated)


# ─── Policy Rules (Priority Engine — User/Position/Department/Organization) ─

@router.get("/policy-rules", response_model=list[PointPolicyRuleResponse], summary="لیست استثناهای امتیازدهی")
async def list_policy_rules(
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
    event_type: str | None = None,
):
    rules = await points_service.list_policy_rules(db, event_type)
    return [await points_service.policy_rule_to_response(db, r) for r in rules]


@router.post(
    "/policy-rules", response_model=PointPolicyRuleResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن استثنای امتیازدهی (User/Position/Department/Organization — قابل ترکیب)",
)
async def create_policy_rule(
    body: PointPolicyRuleCreate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rule = await points_service.create_policy_rule(db, body, current_user.id)
    return await points_service.policy_rule_to_response(db, rule)


@router.patch("/policy-rules/{rule_id}", response_model=PointPolicyRuleResponse, summary="ویرایش استثنای امتیازدهی")
async def update_policy_rule(
    rule_id: str,
    body: PointPolicyRuleUpdate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rule = await points_service.get_policy_rule(db, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "استثنا یافت نشد")
    updated = await points_service.update_policy_rule(db, rule, body, current_user.id)
    return await points_service.policy_rule_to_response(db, updated)


@router.delete("/policy-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف استثنای امتیازدهی")
async def delete_policy_rule(
    rule_id: str,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    rule = await points_service.get_policy_rule(db, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "استثنا یافت نشد")
    await points_service.delete_policy_rule(db, rule, current_user.id)


# ─── Manual Transactions + Org Ledger ──────────────────────────────────────

@router.post(
    "/manual-transactions", response_model=PointsLedgerEntryResponse, status_code=status.HTTP_201_CREATED,
    summary="ثبت تراکنش دستی (امتیاز تشویقی / اصلاح / کسر / اصلاح خطا)",
)
async def create_manual_transaction(
    body: ManualTransactionCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    entry = await points_service.create_manual_transaction(db, body, current_user)
    return await points_service.entry_to_response(db, entry)


@router.get("/ledger", response_model=PointsHistoryResponse, summary="دفترکل امتیازات سازمان")
async def list_org_ledger(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — خالی یعنی سازمان خودش"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    target_org_id = current_user.org_id
    if org_id:
        try:
            target_org_id = uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه‌ی سازمان نامعتبر است")
    enforce_org_scope(current_user, target_org_id)

    items, total = await points_service.list_history_for_org(db, target_org_id, page=page, page_size=page_size)
    responses = [await points_service.entry_to_response(db, e) for e in items]
    return PointsHistoryResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )
