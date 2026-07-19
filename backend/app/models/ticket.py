"""
Talentick — Ticket Models
============================
جداول: ticket_categories, tickets, ticket_messages, ticket_access_grants

تیکت = هر درخواست/بازخورد/سؤال کارمند به مدیر سازمان (درخواست دوره‌ی
جدید، نظر درباره‌ی یک محتوا، مشکل فنی، یا هر چیز دیگر). دسته‌بندی‌ها
سراسری‌اند (نه per-org) و فقط super_admin مدیریتشان می‌کند.

دسترسی پیش‌فرض دیدن/پاسخ‌دادن به تیکت‌های یک سازمان: org_admin همان
سازمان + super_admin (همه‌جا). فراتر از این، super_admin می‌تواند از
طریق TicketAccessGrant به یک نقش خاص (مثل manager) یا یک کاربر خاص در
یک سازمان مشخص، دسترسی اضافه بدهد — این مکانیزم مستقل از واگذاری
تک‌تیکتی است؛ هر کسی که دسترسی دارد به همه‌ی تیکت‌های آن سازمان
دسترسی دارد، نه فقط تیکت‌های واگذارشده به او.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

TICKET_STATUSES = ("open", "answered", "closed")
GRANT_TYPES = ("role", "user")
GRANTABLE_ROLES = ("manager", "employee")


class TicketCategory(UUIDMixin, TimestampMixin, Base):
    """دسته‌بندی تیکت — سراسری، فقط super_admin مدیریت می‌کند."""

    __tablename__ = "ticket_categories"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<TicketCategory name={self.name!r}>"


class Ticket(UUIDMixin, TimestampMixin, Base):
    """تیکت — درخواست/بازخورد/سؤال یک کاربر به مدیران سازمانش."""

    __tablename__ = "tickets"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ticket_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contents.id", ondelete="SET NULL"),
        nullable=True,
        comment="اتصال اختیاری به یک محتوای مشخص — مثلاً نظر درباره‌ی یک دوره",
    )

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open",
        comment="open | answered | closed",
    )
    satisfaction_rating: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="۱ تا ۵ — فقط وقتی کارمند خودش با رضایت می‌بندد",
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ────────────────────────────────────────────────────
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<Ticket subject={self.subject!r} status={self.status!r}>"


class TicketMessage(UUIDMixin, TimestampMixin, Base):
    """یک پیام در ترد گفتگوی یک تیکت."""

    __tablename__ = "ticket_messages"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # ─── Relationships ────────────────────────────────────────────────────
    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class TicketAccessGrant(UUIDMixin, TimestampMixin, Base):
    """
    مجوز دسترسی اضافه به بخش تیکتینگ یک سازمان — فقط super_admin می‌سازد.

    org_admin و super_admin همیشه دسترسی پیش‌فرض دارند و نیازی به grant
    ندارند؛ این جدول فقط برای دادن دسترسی فراتر از پیش‌فرض است (مثلاً به
    یک نقش manager یا یک کاربر خاص).
    """

    __tablename__ = "ticket_access_grants"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grant_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="role | user"
    )
    role: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="فقط وقتی grant_type=role"
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="فقط وقتی grant_type=user",
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<TicketAccessGrant org={self.org_id} type={self.grant_type} role={self.role} user={self.user_id}>"
