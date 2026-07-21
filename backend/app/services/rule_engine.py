"""
Talentick — Gamification Rule Engine (Priority Engine)
===========================================================
محاسبه‌ی مقدار مؤثر امتیاز یک Event برای یک کاربر مشخص — بخش دوم اسپک.

سلسله‌مراتب اولویت (بالاترین اول):

    ۱. User Rule          — point_policy_rules.user_id = کاربر
    ۲. Position Rule      — point_policy_rules.position_id = پست کاربر
    ۳. Department Rule    — point_policy_rules.dept_id = واحد کاربر
    ۴. Organization Rule  — point_policy_rules.org_id = سازمان کاربر
    ۵. Default            — points_override اختصاصیِ خودِ موجودیت (اگر
                             این Event به یک موجودیت وصل است — مثلاً
                             quiz_passed به همان Quiz) و در نبود آن،
                             مقدار سراسری point_rules.event_type

یک Rule می‌تواند چند شرط را هم‌زمان AND کند (مثال اسپک: Organization=X
AND Department=HR AND Position=Manager). سطح (Tier) آن Rule بر اساس
مشخص‌ترین شرط ست‌شده تعیین می‌شود — اگر user_id ست باشد، Rule «سطح User»
است حتی اگر org_id/dept_id/position_id هم هم‌زمان ست باشند، چون شرط‌های
اضافه فقط دامنه‌ی همان Rule سطح‌بالا را تنگ‌تر می‌کنند، سطحش را عوض
نمی‌کنند.

اگر چند Rule هم‌زمان در یک سطح صدق کنند (مثلاً هم یک Rule فقط‌user و
هم Rule دیگری هم‌سطح)، تای‌بریک به این ترتیب است:
    ۱. specificity بیشتر (تعداد شرط‌های ست‌شده) برنده است
    ۲. priority صریح‌تر (عدد بزرگ‌تر) برنده است
    ۳. جدیدترین Rule (created_at بزرگ‌تر) برنده است

points می‌تواند صفر باشد (یعنی «این گروه امتیاز نگیرد» — یک override
عمدی، نه «قانونی وجود ندارد») — صفر با نبود Rule فرق دارد و در ledger
هیچ تراکنشی ثبت نمی‌کند (نه این‌که یعنی از سطح بعدی استفاده شود).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, ContentItem
from app.models.onboarding import OnboardingProgram, ProgramStep
from app.models.points import PointPolicyRule, PointRule
from app.models.quiz import Quiz
from app.models.user import User

# نگاشت Event → (مدل موجودیت مرتبط، نام ستون‌ عنوان برای نمایش در ledger)
# فقط Eventهایی که به یک موجودیت مشخص با ستون points_override وصل‌اند
# اینجا هستند — Event های سفارشی/آینده که super_admin از طریق API اضافه
# می‌کند مستقیم به مقدار سراسری point_rules می‌روند (بدون override اختصاصی).
_REFERENCE_MODEL_MAP: dict[str, tuple[type, str]] = {
    "content_item_completed": (ContentItem, "title"),
    "content_completed": (Content, "title"),
    "quiz_passed": (Quiz, "title"),
    "onboarding_step_completed": (ProgramStep, "title"),
    "onboarding_program_completed": (OnboardingProgram, "name"),
}


@dataclass(frozen=True)
class ResolvedPoints:
    points: int
    source: str            # entity_override | policy_rule:user | policy_rule:position | policy_rule:department | policy_rule:organization | default_rule
    reference_title: str | None = None


def _tier_rank(rule: PointPolicyRule) -> int:
    """۱=User (بالاترین اولویت) ... ۴=Organization (پایین‌ترین اولویت این جدول)."""
    if rule.user_id is not None:
        return 1
    if rule.position_id is not None:
        return 2
    if rule.dept_id is not None:
        return 3
    return 4  # org_id تضمین‌شده ست است — CheckConstraint دیتابیس


def _tier_name(rank: int) -> str:
    return {1: "user", 2: "position", 3: "department", 4: "organization"}[rank]


def _specificity(rule: PointPolicyRule) -> int:
    return sum(x is not None for x in (rule.org_id, rule.dept_id, rule.position_id, rule.user_id))


def _rule_sort_key(rule: PointPolicyRule) -> tuple:
    rank = _tier_rank(rule)
    return (rank, -_specificity(rule), -rule.priority, -rule.created_at.timestamp())


async def _resolve_baseline(
    db: AsyncSession, event_type: str, reference_id: uuid.UUID | None
) -> tuple[int, str, str | None]:
    """سطح ۵ — override اختصاصی موجودیت، وگرنه مقدار سراسری point_rules."""
    mapping = _REFERENCE_MODEL_MAP.get(event_type)
    if mapping and reference_id is not None:
        model, title_field = mapping
        obj = await db.get(model, reference_id)
        if obj is not None:
            title = getattr(obj, title_field, None)
            if obj.points_override is not None:
                return obj.points_override, "entity_override", title
            rule = await db.scalar(select(PointRule).where(PointRule.event_type == event_type))
            if rule and rule.is_active:
                return rule.points, "default_rule", title
            return 0, "default_rule", title

    rule = await db.scalar(select(PointRule).where(PointRule.event_type == event_type))
    if rule and rule.is_active:
        return rule.points, "default_rule", None
    return 0, "default_rule", None


async def resolve_points(
    db: AsyncSession, *, event_type: str, user: User, reference_id: uuid.UUID | None = None
) -> ResolvedPoints:
    """مقدار مؤثر امتیاز این Event برای این کاربر — کل Priority Engine."""
    baseline_points, baseline_source, reference_title = await _resolve_baseline(db, event_type, reference_id)

    candidates_result = await db.execute(
        select(PointPolicyRule).where(
            PointPolicyRule.event_type == event_type,
            PointPolicyRule.is_active.is_(True),
            (PointPolicyRule.org_id.is_(None)) | (PointPolicyRule.org_id == user.org_id),
            (PointPolicyRule.dept_id.is_(None)) | (PointPolicyRule.dept_id == user.dept_id),
            (PointPolicyRule.position_id.is_(None)) | (PointPolicyRule.position_id == user.position_id),
            (PointPolicyRule.user_id.is_(None)) | (PointPolicyRule.user_id == user.id),
        )
    )
    candidates = list(candidates_result.scalars().all())
    if not candidates:
        return ResolvedPoints(points=baseline_points, source=baseline_source, reference_title=reference_title)

    winner = min(candidates, key=_rule_sort_key)
    return ResolvedPoints(
        points=winner.points,
        source=f"policy_rule:{_tier_name(_tier_rank(winner))}",
        reference_title=reference_title,
    )
