"""
Talentick — Announcement Models
===================================
جداول: announcements, announcement_targets

اطلاعیه‌ی تک‌فایلی (عکس/ویدیو) — خارج از سیستم محتوای آموزشی (Content).
برای اطلاع‌رسانی سریع (مثل خبر یا رویداد) که در صفحه‌ی خانه‌ی کارمند،
پیش از بخش‌های آموزشی نمایش داده می‌شود.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# ابعاد کنترل دسترسی — همان منطق document_targets: OR بین department/role،
# بدون هیچ target یعنی برای کل سازمان.
ANNOUNCEMENT_TARGET_TYPES = ("department", "role")
MEDIA_TYPES = ("image", "video")


class Announcement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "announcements"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    media_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="image | video")
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="حجم به بایت")

    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="شروع بازه‌ی نمایش — خالی یعنی از هم‌اکنون"
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="پایان بازه‌ی نمایش — خالی یعنی نامحدود"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    targets: Mapped[list["AnnouncementTarget"]] = relationship(
        back_populates="announcement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Announcement title={self.title!r}>"


class AnnouncementTarget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "announcement_targets"

    __table_args__ = (
        UniqueConstraint(
            "announcement_id", "target_type", "target_value",
            name="uq_announcement_target",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="department | role")
    target_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="UUID برای department — نام role برای role"
    )

    announcement: Mapped["Announcement"] = relationship(back_populates="targets")

    def __repr__(self) -> str:
        return f"<AnnouncementTarget {self.target_type}={self.target_value!r}>"
