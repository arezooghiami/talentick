"""
Talentick — Points (Gamification) Service
=============================================
لایه‌ی سرویس ماژول Point Engine — بخش‌های اول تا چهارم اسپک.

award_points() نقطه‌ی ورود Event Engine است: هر جای دیگر کد (progress_
service، quiz_service، onboarding_service، ...) وقتی یک Event رخ می‌دهد
همین یک تابع را صدا می‌زند — محاسبه‌ی مقدار مؤثر امتیاز به rule_engine
(Priority Engine) و ثبت واقعی تراکنش+به‌روزرسانی کیف‌پول به wallet_
service سپرده شده. این تابع commit نمی‌کند — باید در همان تراکنشی که
خودِ Event را ثبت می‌کند صدا زده شود (اتمیک بودن).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Department, Organization, Position
from app.models.points import (
    PointPolicyRule,
    PointRule,
    PointsLedgerEntry,
    PointWallet,
)
from app.models.user import User
from app.schemas.points import (
    ManualTransactionCreate,
    PointPolicyRuleCreate,
    PointPolicyRuleResponse,
    PointPolicyRuleUpdate,
    PointRuleCreate,
    PointRuleResponse,
    PointRuleUpdate,
    PointsLedgerEntryResponse,
    WalletResponse,
)
from app.services import audit_service, rule_engine, wallet_service

TRANSACTION_TYPE_LABEL_FA = {
    "earn": "کسب امتیاز",
    "bonus": "امتیاز تشویقی",
    "manual_adjustment": "اصلاح دستی",
    "deduction": "کسر امتیاز",
    "reward_redemption": "تبدیل به جایزه",
    "expiration": "انقضای امتیاز",
    "correction": "اصلاح خطا",
}
MANUAL_TRANSACTION_TYPES = ("bonus", "manual_adjustment", "deduction", "correction")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Rules (سراسری — فقط super_admin — Event Driven) ───────────────────────

async def list_rules(db: AsyncSession) -> list[PointRule]:
    result = await db.execute(select(PointRule).order_by(PointRule.event_type))
    return list(result.scalars().all())


async def get_rule(db: AsyncSession, event_type: str) -> PointRule | None:
    return (await db.execute(
        select(PointRule).where(PointRule.event_type == event_type)
    )).scalar_one_or_none()


async def get_rule_by_id(db: AsyncSession, rule_id: str) -> PointRule | None:
    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        return None
    return await db.get(PointRule, rid)


async def create_rule(db: AsyncSession, data: PointRuleCreate, actor_id: uuid.UUID) -> PointRule:
    existing = await get_rule(db, data.event_type)
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این نوع Event از قبل تعریف شده است")
    rule = PointRule(
        id=uuid.uuid4(), event_type=data.event_type, event_label=data.event_label,
        points=data.points, is_active=data.is_active,
    )
    db.add(rule)
    await db.flush()
    await audit_service.log(
        db, org_id=None, actor_id=actor_id, action="rule_created", entity_type="point_rule",
        entity_id=rule.id, after={"event_type": rule.event_type, "points": rule.points},
    )
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_rule(db: AsyncSession, rule: PointRule, data: PointRuleUpdate, actor_id: uuid.UUID) -> PointRule:
    before = {"event_label": rule.event_label, "points": rule.points, "is_active": rule.is_active}
    if data.event_label is not None:
        rule.event_label = data.event_label
    if data.points is not None:
        rule.points = data.points
    if data.is_active is not None:
        rule.is_active = data.is_active
    await db.flush()
    await audit_service.log(
        db, org_id=None, actor_id=actor_id, action="rule_updated", entity_type="point_rule",
        entity_id=rule.id, before=before,
        after={"event_label": rule.event_label, "points": rule.points, "is_active": rule.is_active},
    )
    await db.commit()
    await db.refresh(rule)
    return rule


def rule_to_response(rule: PointRule) -> PointRuleResponse:
    return PointRuleResponse(
        id=str(rule.id), event_type=rule.event_type, event_label=rule.event_label,
        points=rule.points, is_active=rule.is_active,
    )


# ─── Policy Rules (Priority Engine — User/Position/Department/Organization) ─

def _parse_uuid_or_400(value: str | None, field_name: str) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{field_name} نامعتبر است")


async def list_policy_rules(db: AsyncSession, event_type: str | None = None) -> list[PointPolicyRule]:
    q = select(PointPolicyRule).order_by(PointPolicyRule.event_type, PointPolicyRule.created_at.desc())
    if event_type:
        q = q.where(PointPolicyRule.event_type == event_type)
    return list((await db.execute(q)).scalars().all())


async def get_policy_rule(db: AsyncSession, rule_id: str) -> PointPolicyRule | None:
    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        return None
    return await db.get(PointPolicyRule, rid)


async def create_policy_rule(
    db: AsyncSession, data: PointPolicyRuleCreate, actor_id: uuid.UUID
) -> PointPolicyRule:
    org_id = _parse_uuid_or_400(data.org_id, "شناسه‌ی سازمان")
    dept_id = _parse_uuid_or_400(data.dept_id, "شناسه‌ی واحد سازمانی")
    position_id = _parse_uuid_or_400(data.position_id, "شناسه‌ی سمت")
    user_id = _parse_uuid_or_400(data.user_id, "شناسه‌ی کاربر")

    if org_id and not await db.get(Organization, org_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سازمان یافت نشد")
    if dept_id and not await db.get(Department, dept_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد سازمانی یافت نشد")
    if position_id and not await db.get(Position, position_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سمت یافت نشد")
    if user_id and not await db.get(User, user_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر یافت نشد")

    rule = PointPolicyRule(
        id=uuid.uuid4(), event_type=data.event_type, org_id=org_id, dept_id=dept_id,
        position_id=position_id, user_id=user_id, points=data.points,
        priority=data.priority, is_active=data.is_active, created_by=actor_id,
    )
    db.add(rule)
    await db.flush()
    await audit_service.log(
        db, org_id=org_id, actor_id=actor_id, action="policy_rule_created", entity_type="point_policy_rule",
        entity_id=rule.id,
        after={
            "event_type": rule.event_type, "points": rule.points,
            "org_id": str(org_id) if org_id else None, "dept_id": str(dept_id) if dept_id else None,
            "position_id": str(position_id) if position_id else None, "user_id": str(user_id) if user_id else None,
        },
    )
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_policy_rule(
    db: AsyncSession, rule: PointPolicyRule, data: PointPolicyRuleUpdate, actor_id: uuid.UUID
) -> PointPolicyRule:
    before = {"points": rule.points, "priority": rule.priority, "is_active": rule.is_active}
    if data.points is not None:
        rule.points = data.points
    if data.priority is not None:
        rule.priority = data.priority
    if data.is_active is not None:
        rule.is_active = data.is_active
    await db.flush()
    await audit_service.log(
        db, org_id=rule.org_id, actor_id=actor_id, action="policy_rule_updated", entity_type="point_policy_rule",
        entity_id=rule.id, before=before,
        after={"points": rule.points, "priority": rule.priority, "is_active": rule.is_active},
    )
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_policy_rule(db: AsyncSession, rule: PointPolicyRule, actor_id: uuid.UUID) -> None:
    org_id, rule_id, event_type, points = rule.org_id, rule.id, rule.event_type, rule.points
    await db.delete(rule)
    await audit_service.log(
        db, org_id=org_id, actor_id=actor_id, action="policy_rule_deleted", entity_type="point_policy_rule",
        entity_id=rule_id, before={"event_type": event_type, "points": points},
    )
    await db.commit()


async def policy_rule_to_response(db: AsyncSession, rule: PointPolicyRule) -> PointPolicyRuleResponse:
    event_rule = await get_rule(db, rule.event_type)
    event_label = event_rule.event_label if event_rule else rule.event_type
    tier = rule_engine._tier_name(rule_engine._tier_rank(rule))

    org = await db.get(Organization, rule.org_id) if rule.org_id else None
    dept = await db.get(Department, rule.dept_id) if rule.dept_id else None
    position = await db.get(Position, rule.position_id) if rule.position_id else None
    user = await db.get(User, rule.user_id) if rule.user_id else None

    return PointPolicyRuleResponse(
        id=str(rule.id), event_type=rule.event_type, event_label=event_label, tier=tier,
        org_id=str(rule.org_id) if rule.org_id else None, org_name=org.name if org else None,
        dept_id=str(rule.dept_id) if rule.dept_id else None, dept_name=dept.name if dept else None,
        position_id=str(rule.position_id) if rule.position_id else None,
        position_name=position.name if position else None,
        user_id=str(rule.user_id) if rule.user_id else None, user_name=user.full_name if user else None,
        points=rule.points, priority=rule.priority, is_active=rule.is_active, created_at=rule.created_at,
    )


# ─── Awarding (Event Engine — نقطه‌ی ورود همه‌ی Eventهای امتیازآور) ────────

async def award_points(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, event_type: str, reference_id: uuid.UUID
) -> bool:
    """
    اهدای امتیاز برای یک Event — idempotent، commit نمی‌کند.

    مقدار از rule_engine.resolve_points (Priority Engine ۵سطحی) محاسبه
    و از طریق wallet_service.apply_ledger_entry ثبت می‌شود. برمی‌گرداند
    True فقط اگر واقعاً یک تراکنش جدید ثبت شده باشد.
    """
    user = await db.get(User, user_id)
    if not user:
        return False

    resolved = await rule_engine.resolve_points(db, event_type=event_type, user=user, reference_id=reference_id)
    if resolved.points <= 0:
        return False

    entry = await wallet_service.apply_ledger_entry(
        db, org_id=org_id, user_id=user_id, transaction_type="earn", points=resolved.points,
        event_type=event_type, reference_id=reference_id, points_source=resolved.source,
        description=resolved.reference_title,
    )
    return entry is not None


async def create_manual_transaction(
    db: AsyncSession, data: ManualTransactionCreate, actor: User
) -> PointsLedgerEntry:
    if data.transaction_type not in MANUAL_TRANSACTION_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نوع تراکنش نامعتبر — مقادیر مجاز: {', '.join(MANUAL_TRANSACTION_TYPES)}",
        )
    target_user = await db.get(User, _parse_uuid_or_400(data.user_id, "شناسه‌ی کاربر"))
    if not target_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")
    if actor.role != "super_admin" and str(actor.org_id) != str(target_user.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این سازمان مجاز نیست")

    points = data.points
    if data.transaction_type in ("bonus",) and points <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "امتیاز تشویقی باید مثبت باشد")
    if data.transaction_type == "deduction":
        if points <= 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "مقدار کسر باید مثبت وارد شود")
        points = -points
    if points == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مقدار امتیاز نمی‌تواند صفر باشد")

    entry = await wallet_service.apply_ledger_entry(
        db, org_id=target_user.org_id, user_id=target_user.id, transaction_type=data.transaction_type,
        points=points, created_by=actor.id, description=data.description, points_source="manual",
    )
    if entry is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ثبت تراکنش ناموفق بود")

    await audit_service.log(
        db, org_id=target_user.org_id, actor_id=actor.id, action=f"manual_{data.transaction_type}",
        entity_type="points_ledger", entity_id=entry.id,
        after={"user_id": str(target_user.id), "points": points}, note=data.description,
    )
    await db.commit()
    await db.refresh(entry)
    return entry


# ─── Query — کیف‌پول و تاریخچه (نمای شخصی/ادمین) ────────────────────────────

async def get_total_points_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    wallet = await wallet_service.get_wallet(db, user_id)
    return wallet.current_balance if wallet else 0


async def get_wallet_response(db: AsyncSession, user_id: uuid.UUID) -> WalletResponse:
    wallet = await wallet_service.get_wallet(db, user_id)
    if not wallet:
        return WalletResponse(
            current_balance=0, total_earned=0, total_spent=0, total_expired=0,
            pending_points=0, redeemed_points=0,
        )
    return WalletResponse(
        current_balance=wallet.current_balance, total_earned=wallet.total_earned,
        total_spent=wallet.total_spent, total_expired=wallet.total_expired,
        pending_points=wallet.pending_points, redeemed_points=wallet.redeemed_points,
    )


async def get_platform_total_points(db: AsyncSession) -> int:
    total = await db.scalar(select(func.coalesce(func.sum(PointWallet.current_balance), 0)))
    return int(total or 0)


async def list_history_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, page: int = 1, page_size: int = 20
) -> tuple[list[PointsLedgerEntry], int]:
    count_q = select(func.count()).select_from(PointsLedgerEntry).where(PointsLedgerEntry.user_id == user_id)
    total = (await db.execute(count_q)).scalar_one()

    q = (
        select(PointsLedgerEntry)
        .where(PointsLedgerEntry.user_id == user_id)
        .order_by(PointsLedgerEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def list_history_for_org(
    db: AsyncSession, org_id: uuid.UUID, *, page: int = 1, page_size: int = 20
) -> tuple[list[PointsLedgerEntry], int]:
    count_q = select(func.count()).select_from(PointsLedgerEntry).where(PointsLedgerEntry.org_id == org_id)
    total = (await db.execute(count_q)).scalar_one()

    q = (
        select(PointsLedgerEntry)
        .where(PointsLedgerEntry.org_id == org_id)
        .order_by(PointsLedgerEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def entry_to_response(db: AsyncSession, entry: PointsLedgerEntry) -> PointsLedgerEntryResponse:
    if entry.transaction_type == "earn":
        rule = await get_rule(db, entry.event_type)
        event_label = rule.event_label if rule else entry.event_type
        mapping = rule_engine._REFERENCE_MODEL_MAP.get(entry.event_type)
        reference_title = None
        if mapping:
            model, title_field = mapping
            obj = await db.get(model, entry.reference_id)
            reference_title = getattr(obj, title_field) if obj else None
    else:
        event_label = TRANSACTION_TYPE_LABEL_FA.get(entry.transaction_type, entry.transaction_type)
        reference_title = entry.description

    created_by_name = None
    if entry.created_by:
        creator = await db.get(User, entry.created_by)
        created_by_name = creator.full_name if creator else None

    return PointsLedgerEntryResponse(
        id=str(entry.id), transaction_number=entry.transaction_number, transaction_type=entry.transaction_type,
        event_type=entry.event_type, event_label=event_label,
        reference_id=str(entry.reference_id), reference_title=reference_title,
        points=entry.points, balance_before=entry.balance_before, balance_after=entry.balance_after,
        points_source=entry.points_source, description=entry.description,
        created_by=str(entry.created_by) if entry.created_by else None, created_by_name=created_by_name,
        created_at=entry.created_at,
    )
