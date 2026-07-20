"""
Talentick — Points (Gamification) Service
=============================================
award_points() هسته‌ی این ماژول است — با INSERT ... ON CONFLICT DO NOTHING
روی UNIQUE(user_id, event_type, reference_id) به‌صورت اتمیک idempotent
است؛ یعنی هم صداکردن تصادفی چندباره‌ی همان اتفاق (مثلاً retry شبکه) و
هم «فقط بار اول قبولی آزمون» (reference_id = quiz_id، نه attempt_id)
بدون هیچ query جداگانه‌ی exists-check یا ریسک race condition تضمین
می‌شود.

نکته‌ی مهم: award_points() خودش commit نمی‌کند (فقط flush) — باید در
همان تراکنشی فراخوانی شود که خود اتفاق تکمیل (پیشرفت آیتم، قبولی آزمون،
تکمیل مرحله) را ثبت می‌کند، تا اتمیک باشند (یا هر دو ثبت شوند یا هیچ‌کدام).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from app.models.content import Content, ContentItem
from app.models.onboarding import OnboardingProgram, ProgramStep
from app.models.organization import Department
from app.models.points import GROUP_TARGET_TYPES, PointGroupOverride, PointRule, PointsLedgerEntry
from app.models.quiz import Quiz
from app.models.user import VALID_ROLES, User
from app.schemas.points import (
    EVENT_TYPE_LABEL_FA,
    ROLE_LABEL_FA,
    PointGroupOverrideResponse,
    PointRuleResponse,
    PointsLedgerEntryResponse,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Rules (سراسری — فقط super_admin) ──────────────────────────────────────

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


async def update_rule(db: AsyncSession, rule: PointRule, points: int | None, is_active: bool | None) -> PointRule:
    if points is not None:
        rule.points = points
    if is_active is not None:
        rule.is_active = is_active
    await db.commit()
    await db.refresh(rule)
    return rule


def rule_to_response(rule: PointRule) -> PointRuleResponse:
    return PointRuleResponse(
        id=str(rule.id), event_type=rule.event_type,
        event_label=EVENT_TYPE_LABEL_FA.get(rule.event_type, rule.event_type),
        points=rule.points, is_active=rule.is_active,
    )


# ─── Awarding (هسته‌ی سیستم) ────────────────────────────────────────────────

async def _compute_effective_points(
    db: AsyncSession, event_type: str, reference_id: uuid.UUID, user: User
) -> int:
    """
    سیاست سه‌لایه:
      ۱. override اختصاصی خودِ موجودیت (ستون points_override روی خودش)
      ۲. override گروهی (نقش/واحد سازمانی کاربر)
      ۳. مقدار سراسری پیش‌فرض (point_rules)

    اگر هم override اختصاصی و هم override گروهی هم‌زمان صدق کنند، مقدار
    کمتر برنده می‌شود (محتاطانه‌ترین سیاست). اگر هیچ‌کدام صدق نکند، مقدار
    سراسری پیش‌فرض استفاده می‌شود.
    """
    candidates: list[int] = []

    mapping = _REFERENCE_MODEL_MAP.get(event_type)
    if mapping:
        model, _ = mapping
        obj = await db.get(model, reference_id)
        if obj is not None and obj.points_override is not None:
            candidates.append(obj.points_override)

    group_result = await db.execute(
        select(PointGroupOverride).where(
            PointGroupOverride.event_type == event_type,
            PointGroupOverride.is_active.is_(True),
            (
                ((PointGroupOverride.target_type == "role") & (PointGroupOverride.target_value == user.role))
                | (
                    (PointGroupOverride.target_type == "department")
                    & (PointGroupOverride.target_value == (str(user.dept_id) if user.dept_id else None))
                )
            ),
        )
    )
    for override in group_result.scalars().all():
        candidates.append(override.points)

    if candidates:
        return min(candidates)

    rule = await get_rule(db, event_type)
    if not rule or not rule.is_active:
        return 0
    return rule.points


async def award_points(
    db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID, event_type: str, reference_id: uuid.UUID
) -> bool:
    """
    اهدای امتیاز — idempotent (اگر قبلاً برای همین سه‌تایی اهدا شده، کاری
    نمی‌کند). commit نمی‌کند — caller باید در تراکنش خودش commit کند.

    مقدار امتیاز از _compute_effective_points (سیاست پویا: پیش‌فرض سراسری
    ± override اختصاصی موجودیت ± override گروهی نقش/واحد) محاسبه می‌شود،
    نه مستقیماً از point_rules.

    برمی‌گرداند True فقط اگر واقعاً یک ردیف جدید اضافه شده باشد.
    """
    user = await db.get(User, user_id)
    if not user:
        return False

    points = await _compute_effective_points(db, event_type, reference_id, user)
    if points <= 0:
        return False

    stmt = pg_insert(PointsLedgerEntry).values(
        id=uuid.uuid4(), org_id=org_id, user_id=user_id, event_type=event_type,
        reference_id=reference_id, points=points, created_at=_now(),
    ).on_conflict_do_nothing(constraint="uq_points_ledger_event")
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0


# ─── Group Overrides (نقش/واحد سازمانی — سراسری، فقط super_admin) ──────────

async def list_group_overrides(db: AsyncSession, event_type: str | None = None) -> list[PointGroupOverride]:
    q = select(PointGroupOverride).order_by(PointGroupOverride.event_type, PointGroupOverride.target_type)
    if event_type:
        q = q.where(PointGroupOverride.event_type == event_type)
    return list((await db.execute(q)).scalars().all())


async def get_group_override(db: AsyncSession, override_id: str) -> PointGroupOverride | None:
    try:
        oid = uuid.UUID(override_id)
    except ValueError:
        return None
    return await db.get(PointGroupOverride, oid)


async def create_group_override(
    db: AsyncSession, event_type: str, target_type: str, target_value: str, points: int
) -> PointGroupOverride:
    if event_type not in EVENT_TYPE_LABEL_FA:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع اتفاق نامعتبر است")
    if target_type not in GROUP_TARGET_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نوع گروه نامعتبر — مقادیر مجاز: {', '.join(GROUP_TARGET_TYPES)}")
    if target_type == "role" and target_value not in VALID_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نقش نامعتبر است")
    if target_type == "department":
        try:
            dept_uuid = uuid.UUID(target_value)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه‌ی واحد سازمانی نامعتبر است")
        dept = await db.get(Department, dept_uuid)
        if not dept:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد سازمانی یافت نشد")

    existing = (await db.execute(
        select(PointGroupOverride).where(
            PointGroupOverride.event_type == event_type,
            PointGroupOverride.target_type == target_type,
            PointGroupOverride.target_value == target_value,
        )
    )).scalar_one_or_none()
    if existing:
        existing.points = points
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    override = PointGroupOverride(
        id=uuid.uuid4(), event_type=event_type, target_type=target_type,
        target_value=target_value, points=points, is_active=True,
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)
    return override


async def delete_group_override(db: AsyncSession, override: PointGroupOverride) -> None:
    await db.delete(override)
    await db.commit()


async def group_override_to_response(db: AsyncSession, override: PointGroupOverride) -> PointGroupOverrideResponse:
    target_label = None
    if override.target_type == "role":
        target_label = ROLE_LABEL_FA.get(override.target_value, override.target_value)
    elif override.target_type == "department":
        try:
            dept = await db.get(Department, uuid.UUID(override.target_value))
        except ValueError:
            dept = None
        target_label = dept.name if dept else None

    return PointGroupOverrideResponse(
        id=str(override.id), event_type=override.event_type,
        event_label=EVENT_TYPE_LABEL_FA.get(override.event_type, override.event_type),
        target_type=override.target_type, target_value=override.target_value,
        target_label=target_label, points=override.points, is_active=override.is_active,
    )


# ─── Query — نمای شخصی کارمند ───────────────────────────────────────────────

async def get_total_points_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    total = await db.scalar(
        select(func.coalesce(func.sum(PointsLedgerEntry.points), 0)).where(
            PointsLedgerEntry.user_id == user_id
        )
    )
    return int(total or 0)


async def get_platform_total_points(db: AsyncSession) -> int:
    total = await db.scalar(select(func.coalesce(func.sum(PointsLedgerEntry.points), 0)))
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


_REFERENCE_MODEL_MAP = {
    "content_item_completed": (ContentItem, "title"),
    "content_completed": (Content, "title"),
    "quiz_passed": (Quiz, "title"),
    "onboarding_step_completed": (ProgramStep, "title"),
    "onboarding_program_completed": (OnboardingProgram, "name"),
}


async def entry_to_response(db: AsyncSession, entry: PointsLedgerEntry) -> PointsLedgerEntryResponse:
    reference_title = None
    mapping = _REFERENCE_MODEL_MAP.get(entry.event_type)
    if mapping:
        model, title_field = mapping
        obj = await db.get(model, entry.reference_id)
        reference_title = getattr(obj, title_field) if obj else None

    return PointsLedgerEntryResponse(
        id=str(entry.id), event_type=entry.event_type,
        event_label=EVENT_TYPE_LABEL_FA.get(entry.event_type, entry.event_type),
        reference_id=str(entry.reference_id), reference_title=reference_title,
        points=entry.points, created_at=entry.created_at,
    )
