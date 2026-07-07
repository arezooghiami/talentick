"""
Talentick — Content Models
============================
جداول: contents, content_items, user_content_progress, user_item_progress

طراحی قابل توسعه:
  V0:  type = course | article
  V1+: type = podcast | book | ... (فقط یک enum value اضافه می‌شود)

ساختار دو لایه:
  Content      → کانتینر کلی (مثل یک دوره یا مقاله)
  ContentItem  → آیتم‌های داخل آن (درس، فصل، صفحه)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


# ─── Type enums (string — برای انعطاف migration) ──────────────────────────
# نوع محتوا — قابل توسعه بدون تغییر schema
CONTENT_TYPES = ("course", "article", "podcast", "book")

# نوع آیتم داخل محتوا
ITEM_TYPES = ("text", "video", "pdf", "image", "link", "file", "quiz_ref")

# وضعیت محتوا
CONTENT_STATUSES = ("draft", "published", "archived")

# سطح دشواری
CONTENT_LEVELS = ("beginner", "intermediate", "advanced")

# نوع هدف انتشار محتوا (Targeting) — قابل توسعه
# department/position/user → UUID در target_value ذخیره می‌شود
# role                     → یکی از VALID_ROLES (رشته) در target_value ذخیره می‌شود
TARGET_TYPES = ("department", "position", "role", "user")


class Content(UUIDMixin, TimestampMixin, Base):
    """
    محتوای سازمانی — کانتینر اصلی.

    V0: course و article
    آینده: podcast، book بدون تغییر schema — فقط enum value

    هر Content می‌تواند چندین ContentItem داشته باشد.
    """

    __tablename__ = "contents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="کلید اصلی جداسازی سازمان‌ها"
    )

    # ─── محتوا ────────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="course | article | podcast | book"
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="آدرس تصویر کاور در MinIO"
    )

    # ─── متادیتا ──────────────────────────────────────────────────────────
    author: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="نام نویسنده یا مدرس"
    )
    instructor_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="مدرس (برای دوره‌ها)"
    )
    instructor_avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # tags به صورت array ذخیره می‌شود — قابل جستجو
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list,
        comment="تگ‌ها برای فیلتر و جستجو"
    )

    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft",
        comment="draft | published | archived"
    )
    level: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="beginner | intermediate | advanced"
    )

    # مدت زمان کل (برای دوره = مجموع items)
    total_duration_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="مدت زمان کل به دقیقه"
    )
    total_items_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="تعداد آیتم‌ها — برای نمایش سریع"
    )

    # سازنده محتوا
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # اطلاعات اضافی JSON (قابل توسعه)
    meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="اطلاعات اضافی مثل ISBN کتاب، URL پادکست"
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="محتوای ویژه — نمایش در صفحه اول"
    )

    # ─── Relationships ────────────────────────────────────────────────────
    items: Mapped[list["ContentItem"]] = relationship(
        back_populates="content",
        cascade="all, delete-orphan",
        order_by="ContentItem.order_index",
    )
    user_progresses: Mapped[list["UserContentProgress"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )
    targets: Mapped[list["ContentTarget"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Content type={self.type!r} title={self.title!r}>"


class ContentItem(UUIDMixin, TimestampMixin, Base):
    """
    آیتم داخل محتوا — یک درس، فصل، یا صفحه.

    یک دوره می‌تواند چندین آیتم داشته باشد:
    - آیتم 1: ویدیو معرفی
    - آیتم 2: متن توضیحی
    - آیتم 3: PDF ضمیمه
    - آیتم 4: آزمون (quiz_ref)
    """

    __tablename__ = "content_items"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="text | video | pdf | image | link | file | quiz_ref"
    )

    # محتوای متنی (برای type=text)
    body: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="محتوای Rich Text برای type=text"
    )

    # آدرس فایل/لینک
    media_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="آدرس فایل در MinIO یا URL خارجی"
    )

    # برای quiz_ref: شناسه quiz مرتبط
    quiz_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="شناسه Quiz اگر type=quiz_ref باشد"
    )

    duration_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="مدت زمان به دقیقه"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="ترتیب نمایش آیتم‌ها"
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="آیا بدون ثبت‌نام قابل مشاهده است؟"
    )

    # ─── Relationships ────────────────────────────────────────────────────
    content: Mapped["Content"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<ContentItem type={self.type!r} title={self.title!r}>"


class ContentTarget(UUIDMixin, TimestampMixin, Base):
    """
    هدف انتشار محتوا (Targeting).

    هر سطر یک قانون نمایش است: محتوا برای یک دپارتمان/پست/نقش/کاربر
    مشخص منتشر می‌شود. یک محتوا می‌تواند چند سطر (چند هدف مختلف)
    داشته باشد — منطق OR: کافی است کاربر با یکی از سطرها match کند.

    اگر هیچ سطری برای یک محتوا وجود نداشته باشد، یعنی محتوا برای کل
    سازمان (همه کاربران org) قابل مشاهده است (پیش‌فرض قبلی — سازگاری
    با محتواهای قدیمی).
    """

    __tablename__ = "content_targets"

    __table_args__ = (
        UniqueConstraint(
            "content_id", "target_type", "target_value",
            name="uq_content_target",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="department | position | role | user"
    )
    target_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="UUID برای department/position/user — نام role برای role"
    )

    # ─── Relationships ────────────────────────────────────────────────────
    content: Mapped["Content"] = relationship(back_populates="targets")

    def __repr__(self) -> str:
        return f"<ContentTarget {self.target_type}={self.target_value!r}>"


class UserContentProgress(UUIDMixin, TimestampMixin, Base):
    """
    پیشرفت کاربر در هر محتوا.

    یک سطر به ازای هر (user, content) — یکتاست.
    """

    __tablename__ = "user_content_progress"

    __table_args__ = (
        UniqueConstraint("user_id", "content_id", name="uq_user_content"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # آخرین آیتمی که کاربر دیده — برای ادامه از همان‌جا
    last_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_items.id", ondelete="SET NULL"),
        nullable=True,
    )

    completed_items: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_items: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="درصد پیشرفت 0-100"
    )

    started_at: Mapped[datetime | None] = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ────────────────────────────────────────────────────
    content: Mapped["Content"] = relationship(back_populates="user_progresses")