"""
Talentick — Reward Marketplace Router (Admin)
==================================================
بخش پنجم اسپک — مدیریت فروشگاه جایزه. super_admin (هر سازمان یا سراسری)
و org_admin (فقط سازمان خودش) هر دو می‌توانند Reward بسازند/ویرایش کنند.

کاتالوگ کارمند (فقط‌خواندنی، فیلترشده به قابل‌دسترس‌ها) در routers/me.py است.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin
from app.schemas.reward import RewardCreate, RewardListResponse, RewardResponse, RewardUpdate
from app.services import reward_service

router = APIRouter(prefix="/api/rewards", tags=["Reward Marketplace"])


@router.get("", response_model=RewardListResponse, summary="فهرست مدیریتی Rewardها")
async def list_rewards(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — خالی یعنی سراسری‌ها"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
):
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه‌ی سازمان نامعتبر است")

    items, total = await reward_service.list_rewards_for_admin(
        db, current_user, org_id=org_uuid, page=page, page_size=page_size, search=search,
    )
    responses = [await reward_service.reward_to_response(db, r) for r in items]
    return RewardListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=reward_service.total_pages(total, page_size),
    )


@router.post("", response_model=RewardResponse, status_code=status.HTTP_201_CREATED, summary="ساخت Reward جدید")
async def create_reward(
    body: RewardCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "super_admin" and body.org_id and body.org_id != str(current_user.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "فقط اجازه دارید برای سازمان خودتان جایزه بسازید")
    reward = await reward_service.create_reward(db, body, current_user)
    return await reward_service.reward_to_response(db, reward)


@router.patch("/{reward_id}", response_model=RewardResponse, summary="ویرایش Reward")
async def update_reward(
    reward_id: str,
    body: RewardUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    reward = await reward_service.get_reward(db, reward_id)
    if not reward:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    updated = await reward_service.update_reward(db, reward, body, current_user)
    return await reward_service.reward_to_response(db, updated)


@router.delete("/{reward_id}", response_model=RewardResponse, summary="بایگانی Reward (حذف نرم)")
async def archive_reward(
    reward_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    reward = await reward_service.get_reward(db, reward_id)
    if not reward:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    archived = await reward_service.archive_reward(db, reward, current_user)
    return await reward_service.reward_to_response(db, archived)
