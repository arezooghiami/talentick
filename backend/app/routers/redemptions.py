"""
Talentick — Reward Redemption Router (Admin Review Queue)
================================================================
بخش ششم اسپک — بررسی/تایید/رد/تحویل درخواست‌های تبدیل امتیاز.
org_admin فقط صف سازمان خودش، super_admin همه‌جا (با فیلتر org_id).

ثبت درخواست توسط خودِ کارمند در routers/me.py است (POST /api/me/redemptions).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin, enforce_org_scope
from app.schemas.reward import RedemptionDecision, RedemptionListResponse, RedemptionResponse
from app.services import redemption_service

router = APIRouter(prefix="/api/redemptions", tags=["Reward Marketplace"])


@router.get("", response_model=RedemptionListResponse, summary="صف بررسی درخواست‌های تبدیل امتیاز")
async def list_redemptions(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — خالی یعنی همه‌ی سازمان‌ها"),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    target_org_id: uuid.UUID | None
    if current_user.role == "super_admin":
        target_org_id = None
        if org_id:
            try:
                target_org_id = uuid.UUID(org_id)
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه‌ی سازمان نامعتبر است")
    else:
        target_org_id = current_user.org_id
    if target_org_id is not None:
        enforce_org_scope(current_user, target_org_id)

    items, total = await redemption_service.list_redemptions_for_org(
        db, target_org_id, page=page, page_size=page_size, status_filter=status_filter,
    )
    responses = [await redemption_service.redemption_to_response(db, r) for r in items]
    return RedemptionListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=redemption_service.total_pages(total, page_size),
    )


async def _get_redemption_or_404(db: AsyncSession, redemption_id: str):
    redemption = await redemption_service.get_redemption(db, redemption_id)
    if not redemption:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست یافت نشد")
    return redemption


@router.patch("/{redemption_id}/under-review", response_model=RedemptionResponse, summary="انتقال به «در حال بررسی»")
async def move_under_review(
    redemption_id: str,
    body: RedemptionDecision,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_redemption_or_404(db, redemption_id)
    updated = await redemption_service.move_under_review(db, redemption, current_user, body.admin_note)
    return await redemption_service.redemption_to_response(db, updated)


@router.patch("/{redemption_id}/approve", response_model=RedemptionResponse, summary="تایید درخواست (کسر امتیاز + کاهش انبار)")
async def approve_redemption(
    redemption_id: str,
    body: RedemptionDecision,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_redemption_or_404(db, redemption_id)
    updated = await redemption_service.approve_redemption(db, redemption, current_user, body.admin_note)
    return await redemption_service.redemption_to_response(db, updated)


@router.patch("/{redemption_id}/reject", response_model=RedemptionResponse, summary="رد درخواست")
async def reject_redemption(
    redemption_id: str,
    body: RedemptionDecision,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_redemption_or_404(db, redemption_id)
    updated = await redemption_service.reject_redemption(db, redemption, current_user, body.admin_note)
    return await redemption_service.redemption_to_response(db, updated)


@router.patch("/{redemption_id}/deliver", response_model=RedemptionResponse, summary="ثبت تحویل جایزه")
async def deliver_redemption(
    redemption_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_redemption_or_404(db, redemption_id)
    updated = await redemption_service.deliver_redemption(db, redemption, current_user)
    return await redemption_service.redemption_to_response(db, updated)
