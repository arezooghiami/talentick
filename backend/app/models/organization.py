"""
Talentick — Organization Models
================================
جداول: organizations, departments, positions

هر سازمان یک tenant مجزاست.
در V0 فقط یک سازمان داریم، اما org_id روی همه چیز هست.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Organization(UUIDMixin, TimestampMixin, Base):
    """
    جدول اصلی سازمان — هر سطر یک tenant است.

    در V0 فقط یک سطر وجود دارد.
    slug برای subdomain یا شناسه URL استفاده می‌شود.
    """

    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        comment="شناسه یکتا برای URL — مثال: my-company"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="نام رسمی سازمان"
    )
    name_en: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="نام انگلیسی (اختیاری)"
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="آدرس لوگو در MinIO"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="درباره سازمان — نمایش در صفحه معرفی"
    )
    mission: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="ماموریت سازمان"
    )
    vision: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="چشم‌انداز سازمان"
    )
    values: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="ارزش‌های سازمانی"
    )
    culture: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="فرهنگ سازمانی"
    )
    history: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="تاریخچه سازمان"
    )
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # تنظیمات اضافی — JSON flexible
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="تنظیمات سازمان مثل رنگ، فونت، ویژگی‌های فعال"
    )

    # plan: در V0 فقط 'pilot' داریم
    plan: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pilot"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # ─── Relationships ────────────────────────────────────────────────────
    departments: Mapped[list["Department"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="organization"
    )

    def __repr__(self) -> str:
        return f"<Organization slug={self.slug!r} name={self.name!r}>"


class Department(UUIDMixin, TimestampMixin, Base):
    """
    واحدهای سازمانی — ساختار درختی با parent_id.

    مثال: دپارتمان فناوری > تیم بک‌اند
    """

    __tablename__ = "departments"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="کلید اصلی جداسازی سازمان‌ها"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="نام واحد — مثال: واحد فناوری"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ساختار درختی — یک واحد می‌تواند زیرمجموعه واحد دیگری باشد
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        comment="واحد مادر برای ساختار درختی"
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="ترتیب نمایش در چارت سازمانی"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ─── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(back_populates="departments")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Department name={self.name!r} org={self.org_id}>"


class Position(UUIDMixin, TimestampMixin, Base):
    """
    پست‌های سازمانی — مثال: مدیر محصول، توسعه‌دهنده ارشد.

    به هر Department تعلق دارد.
    """

    __tablename__ = "positions"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="عنوان پست — مثال: مدیر محصول"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="سطح سازمانی: 1=کارمند، 5=مدیرعامل"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ─── Relationships ────────────────────────────────────────────────────
    department: Mapped["Department | None"] = relationship(back_populates="positions")

    organization: Mapped["Organization"] = relationship(
        back_populates="positions"
    )

    def __repr__(self) -> str:
        return f"<Position name={self.name!r}>"