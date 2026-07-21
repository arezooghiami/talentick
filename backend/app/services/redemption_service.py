"""
Talentick — Reward Redemption Service
==========================================
بخش ششم اسپک — گردش کامل درخواست تبدیل امتیاز:

    Draft → Submitted → Under Review → Approved/Rejected → (Approved) Delivered
    (لغو در Draft/Submitted/Under Review توسط خودِ کاربر ممکن است)

کسر امتیاز درست بعد از Approved انجام می‌شود (نه در لحظه‌ی ثبت
درخواست) — یعنی موجودی در لحظه‌ی submit رزرو/قفل نمی‌شود؛ کفایت
موجودی و انبار هم در submit (پیام دوستانه‌ی زودهنگام) و هم دوباره،
authoritative، در لحظه‌ی approve بررسی می‌شود.

تمام گذارهای وضعیت طبق REDEMPTION_TRANSITIONS enforce و Audit می‌شوند.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reward import REDEMPTION_TRANSITIONS, Reward, RewardRedemption
from app.models.user import User
from app.schemas.reward import REDEMPTION_STATUS_LABEL_FA, RedemptionCreate, RedemptionResponse
from app.services import audit_service, reward_service, wallet_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_transition(current: str, target: str) -> None:
    allowed = REDEMPTION_TRANSITIONS.get(current, ())
    if target not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"گذار وضعیت نامعتبر: {REDEMPTION_STATUS_LABEL_FA.get(current, current)} → {REDEMPTION_STATUS_LABEL_FA.get(target, target)}",
        )


async def get_redemption(db: AsyncSession, redemption_id: str) -> RewardRedemption | None:
    try:
        rid = uuid.UUID(redemption_id)
    except ValueError:
        return None
    return await db.get(RewardRedemption, rid)


async def create_redemption(db: AsyncSession, user: User, data: RedemptionCreate) -> RewardRedemption:
    reward = await reward_service.get_reward(db, data.reward_id)
    if not reward or (reward.org_id is not None and str(reward.org_id) != str(user.org_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    if not reward_service.is_available(reward):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این جایزه در حال حاضر قابل‌دسترس نیست")
    if reward.inventory_remaining is not None and data.quantity > reward.inventory_remaining:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "موجودی انبار این جایزه کافی نیست")

    cost = reward.cost_points * data.quantity
    wallet = await wallet_service.get_wallet(db, user.id)
    balance = wallet.current_balance if wallet else 0
    if balance < cost:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "موجودی امتیاز شما کافی نیست")

    now = _now()
    status_value = "submitted" if data.submit else "draft"
    redemption = RewardRedemption(
        id=uuid.uuid4(), org_id=user.org_id, user_id=user.id, reward_id=reward.id,
        status=status_value, quantity=data.quantity, cost_points_snapshot=cost,
        user_note=data.user_note, submitted_at=now if data.submit else None,
    )
    db.add(redemption)
    await db.flush()

    if data.submit:
        await wallet_service.adjust_pending(db, user.id, user.org_id, cost)

    await audit_service.log(
        db, org_id=user.org_id, actor_id=user.id,
        action="redemption_submitted" if data.submit else "redemption_draft_created",
        entity_type="reward_redemption", entity_id=redemption.id,
        after={"reward_id": str(reward.id), "cost_points": cost, "status": status_value},
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def submit_redemption(db: AsyncSession, redemption: RewardRedemption, user: User) -> RewardRedemption:
    _assert_transition(redemption.status, "submitted")
    reward = await reward_service.get_reward(db, str(redemption.reward_id))
    if not reward or not reward_service.is_available(reward):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این جایزه دیگر قابل‌دسترس نیست")

    redemption.status = "submitted"
    redemption.submitted_at = _now()
    await wallet_service.adjust_pending(db, redemption.user_id, redemption.org_id, redemption.cost_points_snapshot)

    await audit_service.log(
        db, org_id=redemption.org_id, actor_id=user.id, action="redemption_submitted",
        entity_type="reward_redemption", entity_id=redemption.id, after={"status": "submitted"},
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def cancel_redemption(db: AsyncSession, redemption: RewardRedemption, user: User) -> RewardRedemption:
    if str(redemption.user_id) != str(user.id) and user.role not in ("org_admin", "super_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی مجاز نیست")
    _assert_transition(redemption.status, "cancelled")

    was_pending = redemption.status in ("submitted", "under_review")
    redemption.status = "cancelled"
    redemption.cancelled_at = _now()
    if was_pending:
        await wallet_service.adjust_pending(db, redemption.user_id, redemption.org_id, -redemption.cost_points_snapshot)

    await audit_service.log(
        db, org_id=redemption.org_id, actor_id=user.id, action="redemption_cancelled",
        entity_type="reward_redemption", entity_id=redemption.id, after={"status": "cancelled"},
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


def _enforce_review_scope(actor: User, redemption: RewardRedemption) -> None:
    if actor.role == "super_admin":
        return
    if actor.role != "org_admin" or str(actor.org_id) != str(redemption.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این درخواست مجاز نیست")


async def move_under_review(db: AsyncSession, redemption: RewardRedemption, actor: User, admin_note: str | None) -> RewardRedemption:
    _enforce_review_scope(actor, redemption)
    _assert_transition(redemption.status, "under_review")
    before_status = redemption.status
    redemption.status = "under_review"
    if admin_note:
        redemption.admin_note = admin_note
    await audit_service.log(
        db, org_id=redemption.org_id, actor_id=actor.id, action="redemption_status_changed",
        entity_type="reward_redemption", entity_id=redemption.id,
        before={"status": before_status}, after={"status": "under_review"}, note=admin_note,
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def approve_redemption(db: AsyncSession, redemption: RewardRedemption, actor: User, admin_note: str | None) -> RewardRedemption:
    _enforce_review_scope(actor, redemption)
    _assert_transition(redemption.status, "approved")

    reward = await db.get(Reward, redemption.reward_id)
    if not reward:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جایزه یافت نشد")
    if reward.inventory_remaining is not None and redemption.quantity > reward.inventory_remaining:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "موجودی انبار این جایزه دیگر کافی نیست — رد کنید")

    wallet = await wallet_service.get_wallet(db, redemption.user_id)
    if not wallet or wallet.current_balance < redemption.cost_points_snapshot:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "موجودی امتیاز کاربر دیگر کافی نیست — رد کنید")

    entry = await wallet_service.apply_ledger_entry(
        db, org_id=redemption.org_id, user_id=redemption.user_id, transaction_type="reward_redemption",
        points=-redemption.cost_points_snapshot, reference_id=redemption.id,
        created_by=actor.id, description=f"تبدیل به جایزه: {reward.title}", points_source="manual",
    )
    if entry is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کسر امتیاز ناموفق بود")

    if reward.inventory_remaining is not None:
        reward.inventory_remaining -= redemption.quantity

    was_pending = redemption.status in ("submitted", "under_review")
    redemption.status = "approved"
    redemption.decided_at = _now()
    redemption.decided_by = actor.id
    redemption.ledger_entry_id = entry.id
    if admin_note:
        redemption.admin_note = admin_note
    if was_pending:
        await wallet_service.adjust_pending(db, redemption.user_id, redemption.org_id, -redemption.cost_points_snapshot)

    await audit_service.log(
        db, org_id=redemption.org_id, actor_id=actor.id, action="redemption_approved",
        entity_type="reward_redemption", entity_id=redemption.id, after={"status": "approved"}, note=admin_note,
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def reject_redemption(db: AsyncSession, redemption: RewardRedemption, actor: User, admin_note: str | None) -> RewardRedemption:
    _enforce_review_scope(actor, redemption)
    _assert_transition(redemption.status, "rejected")

    was_pending = redemption.status in ("submitted", "under_review")
    redemption.status = "rejected"
    redemption.decided_at = _now()
    redemption.decided_by = actor.id
    if admin_note:
        redemption.admin_note = admin_note
    if was_pending:
        await wallet_service.adjust_pending(db, redemption.user_id, redemption.org_id, -redemption.cost_points_snapshot)

    await audit_service.log(
        db, org_id=redemption.org_id, actor_id=actor.id, action="redemption_rejected",
        entity_type="reward_redemption", entity_id=redemption.id, after={"status": "rejected"}, note=admin_note,
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


async def deliver_redemption(db: AsyncSession, redemption: RewardRedemption, actor: User) -> RewardRedemption:
    _enforce_review_scope(actor, redemption)
    _assert_transition(redemption.status, "delivered")

    redemption.status = "delivered"
    redemption.delivered_at = _now()
    redemption.delivered_by = actor.id
    await wallet_service.mark_redeemed(db, redemption.user_id, redemption.org_id, redemption.cost_points_snapshot)

    await audit_service.log(
        db, org_id=redemption.org_id, actor_id=actor.id, action="redemption_delivered",
        entity_type="reward_redemption", entity_id=redemption.id, after={"status": "delivered"},
    )
    await db.commit()
    await db.refresh(redemption)
    return redemption


# ─── Listing ──────────────────────────────────────────────────────────────

async def list_redemptions_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, page: int = 1, page_size: int = 20, status_filter: str | None = None
) -> tuple[list[RewardRedemption], int]:
    conditions = [RewardRedemption.user_id == user_id]
    if status_filter:
        conditions.append(RewardRedemption.status == status_filter)
    count_q = select(func.count()).select_from(RewardRedemption).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar_one()
    q = (
        select(RewardRedemption).where(and_(*conditions))
        .order_by(RewardRedemption.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = list((await db.execute(q)).scalars().all())
    return items, total


async def list_redemptions_for_org(
    db: AsyncSession, org_id: uuid.UUID | None, *, page: int = 1, page_size: int = 20, status_filter: str | None = None
) -> tuple[list[RewardRedemption], int]:
    """org_id=None فقط برای super_admin معتبر است — یعنی صف تمام سازمان‌ها (دید کامل اکوسیستم)."""
    conditions = []
    if org_id is not None:
        conditions.append(RewardRedemption.org_id == org_id)
    if status_filter:
        conditions.append(RewardRedemption.status == status_filter)
    else:
        # پیش‌نویس‌های ثبت‌نشده خصوصی کارمند است — تا وقتی ارسال نشده در صف بررسی ادمین دیده نمی‌شود
        conditions.append(RewardRedemption.status != "draft")
    count_q = select(func.count()).select_from(RewardRedemption).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar_one()
    q = (
        select(RewardRedemption).where(and_(*conditions))
        .order_by(RewardRedemption.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = list((await db.execute(q)).scalars().all())
    return items, total


async def redemption_to_response(db: AsyncSession, redemption: RewardRedemption) -> RedemptionResponse:
    reward = await db.get(Reward, redemption.reward_id)
    user = await db.get(User, redemption.user_id)
    decided_by_user = await db.get(User, redemption.decided_by) if redemption.decided_by else None
    delivered_by_user = await db.get(User, redemption.delivered_by) if redemption.delivered_by else None

    return RedemptionResponse(
        id=str(redemption.id), org_id=str(redemption.org_id), user_id=str(redemption.user_id),
        user_name=user.full_name if user else None, reward_id=str(redemption.reward_id),
        reward_title=reward.title if reward else None, reward_image_url=reward.image_url if reward else None,
        status=redemption.status, status_label=REDEMPTION_STATUS_LABEL_FA.get(redemption.status, redemption.status),
        quantity=redemption.quantity, cost_points_snapshot=redemption.cost_points_snapshot,
        user_note=redemption.user_note, admin_note=redemption.admin_note,
        submitted_at=redemption.submitted_at, decided_at=redemption.decided_at,
        delivered_at=redemption.delivered_at, cancelled_at=redemption.cancelled_at,
        decided_by_name=decided_by_user.full_name if decided_by_user else None,
        delivered_by_name=delivered_by_user.full_name if delivered_by_user else None,
        created_at=redemption.created_at,
    )


def total_pages(total: int, page_size: int) -> int:
    return max(1, math.ceil(total / page_size))
