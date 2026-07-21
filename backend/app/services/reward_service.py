"""
Talentick — Reward Marketplace Service
===========================================
بخش پنجم اسپک — فروشگاه جایزه. یک Reward می‌تواند سراسری باشد (org_id
خالی — فقط super_admin) یا مختص یک سازمان (org_id ست — super_admin یا
org_admin همان سازمان).
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.reward import Reward
from app.models.user import User
from app.schemas.reward import REWARD_CATEGORY_LABEL_FA, RewardCreate, RewardResponse, RewardUpdate
from app.services import audit_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_available(reward: Reward, *, at: datetime | None = None) -> bool:
    at = at or _now()
    if reward.status != "active":
        return False
    if reward.start_date and at < reward.start_date:
        return False
    if reward.end_date and at > reward.end_date:
        return False
    if reward.inventory_remaining is not None and reward.inventory_remaining <= 0:
        return False
    return True


async def get_reward(db: AsyncSession, reward_id: str) -> Reward | None:
    try:
        rid = uuid.UUID(reward_id)
    except ValueError:
        return None
    return await db.get(Reward, rid)


async def list_rewards_for_catalog(
    db: AsyncSession, org_id: uuid.UUID, *, page: int = 1, page_size: int = 20,
    search: str | None = None, category: str | None = None,
) -> tuple[list[Reward], int]:
    """کاتالوگ کارمند — Rewardهای سازمان خودش + سراسری، فقط قابل‌دسترس در همین لحظه."""
    now = _now()
    conditions = [
        or_(Reward.org_id == org_id, Reward.org_id.is_(None)),
        Reward.status == "active",
        or_(Reward.start_date.is_(None), Reward.start_date <= now),
        or_(Reward.end_date.is_(None), Reward.end_date >= now),
        or_(Reward.inventory_remaining.is_(None), Reward.inventory_remaining > 0),
    ]
    if search:
        conditions.append(Reward.title.ilike(f"%{search}%"))
    if category:
        conditions.append(Reward.category == category)

    count_q = select(func.count()).select_from(Reward).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar_one()

    q = (
        select(Reward).where(and_(*conditions))
        .order_by(Reward.cost_points)
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = list((await db.execute(q)).scalars().all())
    return items, total


async def list_rewards_for_admin(
    db: AsyncSession, actor: User, *, org_id: uuid.UUID | None = None,
    page: int = 1, page_size: int = 20, search: str | None = None,
) -> tuple[list[Reward], int]:
    """فهرست مدیریتی — super_admin همه‌جا (با فیلتر اختیاری org_id)، org_admin فقط سازمان خودش + سراسری‌ها."""
    conditions = []
    if actor.role == "super_admin":
        if org_id is not None:
            conditions.append(Reward.org_id == org_id)
    else:
        conditions.append(or_(Reward.org_id == actor.org_id, Reward.org_id.is_(None)))
    if search:
        conditions.append(Reward.title.ilike(f"%{search}%"))

    q_base = select(Reward)
    if conditions:
        q_base = q_base.where(and_(*conditions))

    count_q = select(func.count()).select_from(Reward)
    if conditions:
        count_q = count_q.where(and_(*conditions))
    total = (await db.execute(count_q)).scalar_one()

    q = q_base.order_by(Reward.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list((await db.execute(q)).scalars().all())
    return items, total


def _resolve_scope_org_id(actor: User, requested_org_id: str | None) -> uuid.UUID | None:
    """org_admin همیشه محدود به سازمان خودش — super_admin می‌تواند سراسری (None) یا هر سازمانی بسازد."""
    if actor.role != "super_admin":
        return actor.org_id
    if requested_org_id is None:
        return None
    try:
        return uuid.UUID(requested_org_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه‌ی سازمان نامعتبر است")


async def create_reward(db: AsyncSession, data: RewardCreate, actor: User) -> Reward:
    org_id = _resolve_scope_org_id(actor, data.org_id)
    if org_id and not await db.get(Organization, org_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سازمان یافت نشد")

    reward = Reward(
        id=uuid.uuid4(), org_id=org_id, title=data.title, description=data.description,
        category=data.category, image_url=data.image_url, cost_points=data.cost_points,
        inventory_total=data.inventory_total, inventory_remaining=data.inventory_total,
        start_date=data.start_date, end_date=data.end_date, status=data.status, created_by=actor.id,
    )
    db.add(reward)
    await db.flush()
    await audit_service.log(
        db, org_id=org_id, actor_id=actor.id, action="reward_created", entity_type="reward",
        entity_id=reward.id, after={"title": reward.title, "cost_points": reward.cost_points},
    )
    await db.commit()
    await db.refresh(reward)
    return reward


def _enforce_reward_scope(actor: User, reward: Reward) -> None:
    if actor.role == "super_admin":
        return
    if reward.org_id is None or str(reward.org_id) != str(actor.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این جایزه مجاز نیست")


async def update_reward(db: AsyncSession, reward: Reward, data: RewardUpdate, actor: User) -> Reward:
    _enforce_reward_scope(actor, reward)
    before = {"title": reward.title, "cost_points": reward.cost_points, "status": reward.status}

    payload = data.model_dump(exclude_unset=True)
    if "inventory_total" in payload and payload["inventory_total"] != reward.inventory_total:
        delta = (payload["inventory_total"] or 0) - (reward.inventory_total or 0)
        reward.inventory_remaining = None if payload["inventory_total"] is None else max(
            0, (reward.inventory_remaining or 0) + delta
        )
    for field, value in payload.items():
        setattr(reward, field, value)

    await db.flush()
    await audit_service.log(
        db, org_id=reward.org_id, actor_id=actor.id, action="reward_updated", entity_type="reward",
        entity_id=reward.id, before=before,
        after={"title": reward.title, "cost_points": reward.cost_points, "status": reward.status},
    )
    await db.commit()
    await db.refresh(reward)
    return reward


async def archive_reward(db: AsyncSession, reward: Reward, actor: User) -> Reward:
    _enforce_reward_scope(actor, reward)
    reward.status = "archived"
    await db.flush()
    await audit_service.log(
        db, org_id=reward.org_id, actor_id=actor.id, action="reward_archived", entity_type="reward",
        entity_id=reward.id,
    )
    await db.commit()
    await db.refresh(reward)
    return reward


async def reward_to_response(db: AsyncSession, reward: Reward) -> RewardResponse:
    org = await db.get(Organization, reward.org_id) if reward.org_id else None
    return RewardResponse(
        id=str(reward.id), org_id=str(reward.org_id) if reward.org_id else None,
        org_name=org.name if org else None, title=reward.title, description=reward.description,
        category=reward.category, category_label=REWARD_CATEGORY_LABEL_FA.get(reward.category, reward.category),
        image_url=reward.image_url, cost_points=reward.cost_points,
        inventory_total=reward.inventory_total, inventory_remaining=reward.inventory_remaining,
        start_date=reward.start_date, end_date=reward.end_date, status=reward.status,
        is_available=is_available(reward), created_at=reward.created_at,
    )


def total_pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))
