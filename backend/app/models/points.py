"""
Talentick — Points (Gamification) Models
============================================
جداول: point_rules, point_policy_rules, points_ledger, point_wallets, gamification_audit_logs

سیستم امتیاز — برای هر Event (مشاهده/تکمیل محتوا، قبولی آزمون، تکمیل
مرحله‌ی آنبوردینگ و هر Event دیگری که در آینده اضافه شود) یک ردیف در
points_ledger ثبت می‌شود. مقدار امتیاز از یک Priority Engine ۵سطحی
محاسبه می‌شود (app/services/rule_engine.py):

  ۱. User Rule          — بالاترین اولویت (point_policy_rules.user_id)
  ۲. Position Rule      (point_policy_rules.position_id)
  ۳. Department Rule    (point_policy_rules.dept_id)
  ۴. Organization Rule  (point_policy_rules.org_id)
  ۵. Default Rule       — باقیمانده override اختصاصیِ خودِ موجودیت
                          (ستون points_override روی خود Quiz/Content/...)
                          و در نبود آن، مقدار سراسری point_rules.

اگر چند PointPolicyRule هم‌زمان صدق کنند، بالاترین سطح (پایین‌ترین شماره
در فهرست بالا) برنده است؛ در تساوی سطح، Rule با شرط‌های بیشتر (specificity)
و سپس priority صریح‌تر و در نهایت جدیدترین Rule برنده می‌شود — به‌طور
کامل در rule_engine.resolve_points مستندسازی شده.

قانون طلایی: هیچ موجودی کیف‌پول (PointWallet) هرگز مستقیماً تغییر
نمی‌کند — تنها راه تغییر، از طریق wallet_service.apply_ledger_entry()
است که هم‌زمان یک ردیف در points_ledger ثبت می‌کند. هیچ تغییری بدون Log
امکان‌پذیر نیست (GamificationAuditLog برای تغییر Ruleها/Rewardها/تصمیم‌
روی درخواست‌های تبدیل امتیاز).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# ─── Event Types ────────────────────────────────────────────────────────────
# سیستم Event Driven است — point_rules یک جدول باز است، نه enum ثابت:
# super_admin از طریق POST /api/points/rules می‌تواند هر event_type دلخواه
# (برای هر Event فعلی یا آینده‌ی سیستم — مشاهده محتوا، آپلود مدارک، شرکت در
# نظرسنجی، انجام مأموریت، ...) با یک برچسب فارسی دلخواه اضافه کند، بدون
# نیاز به تغییر کد. این تاپل فقط event_typeهایی را مشخص می‌کند که به یک
# ستون points_override اختصاصی روی موجودیت مرتبط (Quiz/Content/...) وصل‌اند
# و از قبل توسط کدِ محصول در نقطه‌ی وقوعشان emit می‌شوند — رجوع کنید به
# rule_engine._REFERENCE_MODEL_MAP.
CORE_EVENT_TYPES = (
    "content_item_completed",
    "content_completed",
    "quiz_passed",
    "onboarding_step_completed",
    "onboarding_program_completed",
)

# ─── Ledger Transaction Types (بخش چهارم اسپک — دفتر کل امتیازات) ──────────
TRANSACTION_TYPES = (
    "earn",               # کسب امتیاز خودکار از یک Event
    "bonus",               # امتیاز تشویقی دستی (مثبت)
    "manual_adjustment",   # اصلاح دستی (مثبت یا منفی)
    "deduction",            # کسر دستی (منفی)
    "reward_redemption",    # کسر بابت تبدیل به جایزه (منفی)
    "expiration",            # انقضای امتیاز — ساختار آماده، منطق خودکار در این فاز پیاده نشده
    "correction",            # اصلاح خطای گذشته (مثبت یا منفی)
)

# ─── Policy Rule scope tiers (بخش دوم/اولویت اسپک) ─────────────────────────
POLICY_RULE_TIERS = ("user", "position", "department", "organization")


class PointRule(UUIDMixin, TimestampMixin, Base):
    """
    مقدار پیش‌فرض سراسری هر نوع Event — سطح ۵ (Default) — فقط super_admin.

    event_type یک enum ثابت نیست — super_admin می‌تواند ردیف جدید با هر
    event_type/event_label دلخواه بسازد (نظام Event Driven — بخش اول
    اسپک). event_label این‌جا ذخیره می‌شود (نه در کد) تا event_type های
    سفارشی هم برچسب فارسی داشته باشند.
    """

    __tablename__ = "point_rules"

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    event_label: Mapped[str] = mapped_column(String(100), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<PointRule event_type={self.event_type!r} points={self.points}>"


class PointPolicyRule(UUIDMixin, TimestampMixin, Base):
    """
    استثنای امتیازدهی — سطح ۱ تا ۴ (User/Position/Department/Organization).

    هر Rule حداقل یکی از org_id/dept_id/position_id/user_id را ست می‌کند
    (می‌توانند هم‌زمان هم ست باشند — مثال اسپک: Organization=X AND
    Department=HR AND Position=Manager). سطح Rule بر اساس مشخص‌ترین شرط
    ست‌شده تعیین می‌شود (اگر user_id ست باشد یعنی سطح User، حتی اگر
    org_id/dept_id/position_id هم هم‌زمان ست باشند) — منطق کامل در
    rule_engine.py.

    فقط super_admin مدیریت می‌کند (سیاست‌گذاری امتیاز کاملاً متمرکز است).
    """

    __tablename__ = "point_policy_rules"
    __table_args__ = (
        CheckConstraint(
            "org_id IS NOT NULL OR dept_id IS NOT NULL OR position_id IS NOT NULL OR user_id IS NOT NULL",
            name="ck_point_policy_rule_has_scope",
        ),
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True
    )
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True
    )
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("positions.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    points: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="تای‌بریک صریح دستی برای Ruleهای هم‌سطح با specificity برابر — بزرگ‌تر برنده است",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<PointPolicyRule event={self.event_type} points={self.points}>"


class PointsLedgerEntry(UUIDMixin, Base):
    """
    یک ردیف دفترکل امتیاز — همیشه add-only (هیچ‌وقت update/delete نمی‌شود).

    تنها راه ایجاد ردیف، wallet_service.apply_ledger_entry() است — هیچ
    کد دیگری مجاز به INSERT مستقیم روی این جدول نیست، چون این تابع است
    که balance_before/balance_after را قفل‌شده (row lock روی PointWallet)
    محاسبه و شماره‌ی تراکنش را صادر می‌کند.

    points مقدار واقعی لحظه‌ی تراکنش را ذخیره می‌کند (نه ارجاع زنده به
    Rule) — تغییر بعدی یک Rule توسط super_admin نباید تاریخچه را عوض کند.
    می‌تواند منفی باشد (deduction/reward_redemption/expiration/correction).
    """

    __tablename__ = "points_ledger"
    __table_args__ = (
        UniqueConstraint("user_id", "event_type", "reference_id", name="uq_points_ledger_event"),
    )

    transaction_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False, default="earn")

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="برای earn: یکی از EVENT_TYPES — برای بقیه‌ی انواع تراکنش برابر با transaction_type",
    )
    reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
        comment="شناسه‌ی موجودیت مرتبط (content/quiz/.../redemption) یا uuid4 تصادفی برای تراکنش‌های دستی",
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    points_source: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="ردیابی منشا مقدار امتیاز: entity_override | policy_rule:<tier> | default_rule | manual",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="null یعنی سیستم (اهدای خودکار) — برای دستی همیشه پر است",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PointsLedgerEntry user={self.user_id} type={self.transaction_type} points={self.points}>"


class PointWallet(UUIDMixin, Base):
    """
    کیف پول امتیاز — یک ردیف به‌ازای هر کاربر.

    هرگز مستقیم UPDATE نشود — فقط wallet_service.apply_ledger_entry()
    اجازه‌ی تغییر این ردیف را دارد (همراه با ثبت ردیف Ledger متناظر).
    """

    __tablename__ = "point_wallets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    current_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_expired: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="مجموع امتیاز درخواست‌های تبدیل در وضعیت submitted/under_review — صرفاً اطلاعاتی، امتیاز رزرو/قفل نمی‌شود",
    )
    redeemed_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="مجموع امتیاز جوایز delivered شده",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PointWallet user={self.user_id} balance={self.current_balance}>"


class GamificationAuditLog(UUIDMixin, Base):
    """
    Audit Trail سراسری ماژول Gamification — بخش یازدهم اسپک.

    هر تغییر در Ruleها، Rewardها و هر تصمیم روی درخواست‌های تبدیل امتیاز
    یک ردیف اینجا ثبت می‌کند؛ مستقل از points_ledger (که فقط تراکنش‌های
    امتیاز را نگه می‌دارد، نه تصمیمات/تغییرات ساختاری).
    """

    __tablename__ = "gamification_audit_logs"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="null یعنی سیستم",
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<GamificationAuditLog action={self.action!r} entity={self.entity_type}:{self.entity_id}>"
