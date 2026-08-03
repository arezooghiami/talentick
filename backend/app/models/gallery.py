"""
Talentick — Gallery Models
=============================
جداول: galleries, gallery_photos

مجموعه‌ی عکس (گالری) — خارج از سیستم محتوای آموزشی (Content)، مثل
Announcement/Document از یک org_id nullable برای Public/سازمان‌خاص
استفاده می‌کند اما بدون سیستم targeting (بخش/نقش)، چون کاربر فقط
public/سازمان‌خاص خواسته، نه هدف‌گذاری ریزتر.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Gallery(UUIDMixin, TimestampMixin, Base):
    """یک مجموعه‌ی عکس — عنوان، توضیحات، کاور و چند عکس."""

    __tablename__ = "galleries"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL یعنی گالری Public/General (فقط super_admin می‌سازد)"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    photos: Mapped[list["GalleryPhoto"]] = relationship(
        back_populates="gallery",
        cascade="all, delete-orphan",
        order_by="GalleryPhoto.order_index",
    )

    def __repr__(self) -> str:
        return f"<Gallery title={self.title!r}>"


class GalleryPhoto(UUIDMixin, TimestampMixin, Base):
    """یک عکس داخل گالری — فقط تصویر + ترتیب نمایش."""

    __tablename__ = "gallery_photos"

    gallery_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("galleries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    gallery: Mapped["Gallery"] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return f"<GalleryPhoto gallery_id={self.gallery_id!r} order={self.order_index!r}>"
