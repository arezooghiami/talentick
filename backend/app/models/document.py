"""
Talentick — Document Library Models
======================================
جداول: document_categories, documents, document_targets

کتابخانه‌ی اسناد سازمانی — قوانین، آیین‌نامه‌ها و مستندات داخلی.
فایل واقعی در MinIO ذخیره می‌شود (app.core.storage.upload_file)؛ این
جداول فقط متادیتا و قوانین دسترسی را نگه می‌دارند.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    pass

# ابعاد کنترل دسترسی سند — منطق OR: بدون target یعنی برای کل سازمان.
# اگر target ثبت شده باشد، کاربر باید حداقل با یکی (department یا role) مطابقت داشته باشد.
DOCUMENT_TARGET_TYPES = ("department", "role")


class DocumentCategory(UUIDMixin, TimestampMixin, Base):
    """دسته‌بندی اسناد — مثال: قوانین، آیین‌نامه‌ها، فرم‌ها."""

    __tablename__ = "document_categories"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<DocumentCategory name={self.name!r}>"


class Document(UUIDMixin, TimestampMixin, Base):
    """یک سند در کتابخانه — قانون/آیین‌نامه/مستند سازمانی."""

    __tablename__ = "documents"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="حجم به بایت")
    file_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="پسوند فایل — pdf | doc | docx | ..."
    )

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ─── Relationships ────────────────────────────────────────────────────
    category: Mapped["DocumentCategory | None"] = relationship(back_populates="documents")
    targets: Mapped[list["DocumentTarget"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document title={self.title!r}>"


class DocumentTarget(UUIDMixin, TimestampMixin, Base):
    """
    قانون دسترسی سند (Permission Engine ساده).

    منطق: بدون هیچ target = قابل مشاهده برای کل سازمان.
    با وجود target: کاربر باید در حداقل یکی از واحدهای انتخاب‌شده باشد
    یا نقشش در نقش‌های انتخاب‌شده باشد (OR بین همه‌ی سطرها).
    """

    __tablename__ = "document_targets"

    __table_args__ = (
        UniqueConstraint(
            "document_id", "target_type", "target_value",
            name="uq_document_target",
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="department | role"
    )
    target_value: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="UUID برای department — نام role برای role"
    )

    document: Mapped["Document"] = relationship(back_populates="targets")

    def __repr__(self) -> str:
        return f"<DocumentTarget {self.target_type}={self.target_value!r}>"
