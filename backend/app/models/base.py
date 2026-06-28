"""
Talentick — Base SQLAlchemy Model
====================================
تمام مدل‌ها از این کلاس ارث می‌برند.

قوانین طلایی:
- UUID برای PK — هرگز integer نه
- timestamptz برای زمان — هرگز timestamp بدون timezone نه
- org_id روی تمام جداول — Row-Level Security منطقی
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class برای تمام مدل‌های SQLAlchemy."""
    pass


class TimestampMixin:
    """
    created_at و updated_at را به مدل اضافه می‌کند.
    updated_at به صورت خودکار هنگام update تغییر می‌کند.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """UUID primary key — امن‌تر و قابل scale از integer."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )