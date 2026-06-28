"""
Talentick — User Models
========================
جداول: users, refresh_tokens, invitations

نقش‌ها (role enum):
  super_admin — دسترسی کامل به همه سازمان‌ها (برای خود Talentick)
  org_admin   — مدیر سازمان — همه چیز سازمان خودش
  manager     — مدیر واحد — کارمندان واحد خودش
  employee    — کارمند — فقط محتوا و onboarding خودش
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


# ─── Role enum (string — نه Python Enum تا migration راحت‌تر باشد) ─────────
# مقادیر مجاز: super_admin | org_admin | manager | employee
VALID_ROLES = {"super_admin", "org_admin", "manager", "employee"}


class User(UUIDMixin, TimestampMixin, Base):
    """
    کاربران سیستم.

    قانون مهم: هر کاربر به یک org تعلق دارد.
    هرگز org_id را بدون بررسی رد نکنید.
    """

    __tablename__ = "users"

    # ─── سازمان ───────────────────────────────────────────────────────────
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="سازمان کاربر — Row-Level Security"
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="مدیر مستقیم کاربر"
    )
    # ─── اطلاعات اصلی ─────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        index=True,
        comment="ایمیل یکتا در سطح سیستم (نه فقط سازمان)"
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="نام و نام خانوادگی"
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="bcrypt hash — هرگز plain text ذخیره نکنید"
    )

    # ─── نقش و موقعیت ─────────────────────────────────────────────────────
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="employee",
        comment="super_admin | org_admin | manager | employee"
    )
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ─── پروفایل ──────────────────────────────────────────────────────────
    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="آدرس تصویر پروفایل در MinIO"
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── وضعیت ────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="غیرفعال کردن بدون حذف"
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    department: Mapped["Department | None"] = relationship()
    position: Mapped["Position | None"] = relationship()

    def __repr__(self) -> str:
        return f"<User email={self.email!r} role={self.role!r}>"

    @property
    def is_admin(self) -> bool:
        return self.role in ("super_admin", "org_admin")

    @property
    def is_manager(self) -> bool:
        return self.role in ("super_admin", "org_admin", "manager")


class RefreshToken(UUIDMixin, Base):
    """
    Refresh token های ذخیره‌شده در DB.

    هنگام logout یا تغییر پسورد، همه توکن‌های کاربر revoke می‌شوند.
    توکن‌های منقضی شده باید به صورت دوره‌ای از DB پاک شوند.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="برای جداسازی سریع‌تر query"
    )

    # token را hash شده ذخیره می‌کنیم — نه plain text
    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True,
        comment="SHA256 hash از refresh token"
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="زمان revoke — اگر null باشد هنوز معتبر است"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ─── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_valid(self) -> bool:
        from datetime import UTC

        from datetime import datetime as dt
        return (
            self.revoked_at is None
            and self.expires_at > dt.now(UTC)
        )


class Invitation(UUIDMixin, TimestampMixin, Base):
    """
    دعوت‌نامه برای کاربران جدید.

    token یکبار مصرف است و بعد از 72 ساعت منقضی می‌شود.
    """

    __tablename__ = "invitations"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="کاربری که دعوت فرستاده"
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="employee")
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # token یکبار مصرف — UUID random
    token: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True,
        comment="توکن یکبار مصرف برای ثبت‌نام"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="72 ساعت بعد از ارسال منقضی می‌شود"
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="زمان قبول دعوت — null یعنی هنوز استفاده نشده"
    )

    def __repr__(self) -> str:
        return f"<Invitation email={self.email!r} org={self.org_id}>"