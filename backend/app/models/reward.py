"""
Talentick — Reward Marketplace Models
=========================================
جداول: rewards, reward_redemptions

بخش پنجم/ششم اسپک — فروشگاه و تبدیل امتیاز. یک Reward می‌تواند سراسری
باشد (org_id = null → روی همه‌ی سازمان‌ها قابل‌مشاهده، فقط super_admin
می‌سازد) یا مختص یک سازمان (org_id ست، توسط super_admin یا org_admin
همان سازمان ساخته می‌شود).

گردش تبدیل: draft → submitted → under_review → approved/rejected →
(approved) delivered، یا cancel در هر سه وضعیت اول. کسر امتیاز درست بعد
از approved (نه در لحظه‌ی ثبت درخواست) طبق گردش‌کار اسپک انجام می‌شود —
یعنی موجودی کاربر در لحظه‌ی submit رزرو/قفل نمی‌شود؛ کفایت موجودی و
انبار دوباره در لحظه‌ی approve بررسی می‌شود.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

REWARD_CATEGORIES = (
    "goods", "gift_card", "cash", "course", "benefit", "special_access", "leave", "custom",
)
REWARD_STATUSES = ("draft", "active", "inactive", "archived")

REDEMPTION_STATUSES = (
    "draft", "submitted", "under_review", "approved", "rejected", "delivered", "cancelled",
)
# گذارهای مجاز — منبع کنترل واحد state machine در redemption_service.py
REDEMPTION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("submitted", "cancelled"),
    "submitted": ("under_review", "approved", "rejected", "cancelled"),
    "under_review": ("approved", "rejected", "cancelled"),
    "approved": ("delivered",),
    "rejected": (),
    "delivered": (),
    "cancelled": (),
}


class Reward(UUIDMixin, TimestampMixin, Base):
    """یک قلم در فروشگاه جایزه — بخش پنجم اسپک."""

    __tablename__ = "rewards"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True,
        comment="null یعنی سراسری (روی همه‌ی سازمان‌ها) — فقط super_admin می‌تواند null بگذارد",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="custom")
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cost_points: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_total: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="null یعنی نامحدود")
    inventory_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Reward title={self.title!r} cost={self.cost_points}>"


class RewardRedemption(UUIDMixin, TimestampMixin, Base):
    """یک درخواست تبدیل امتیاز به جایزه — بخش ششم اسپک."""

    __tablename__ = "reward_redemptions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    reward_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rewards.id", ondelete="RESTRICT"), nullable=False, index=True,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted", index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cost_points_snapshot: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="quantity × reward.cost_points در لحظه‌ی ثبت — بعداً تغییر قیمت جایزه اثر نمی‌گذارد",
    )

    user_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    delivered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ledger_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("points_ledger.id", ondelete="SET NULL"), nullable=True,
        comment="ردیف کسر امتیاز — فقط بعد از approved پر می‌شود",
    )

    def __repr__(self) -> str:
        return f"<RewardRedemption user={self.user_id} reward={self.reward_id} status={self.status!r}>"
