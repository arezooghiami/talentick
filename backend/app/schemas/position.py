"""
Talentick — Position Schemas
===============================
پست‌های سازمانی (مثل «مدیر محصول»). هر Position می‌تواند به یک
Department تعلق داشته باشد و level سلسله‌مراتبی دارد (۱=کارمند، ۵=مدیرعامل).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    dept_id: str | None = None
    level: int = Field(1, ge=1, le=5)
    org_id: str | None = None  # فقط super_admin — در router enforce می‌شود


class PositionUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    dept_id: str | None = None
    level: int | None = Field(None, ge=1, le=5)
    is_active: bool | None = None


class PositionResponse(BaseModel):
    id: str
    org_id: str
    dept_id: str | None = None
    dept_name: str | None = None
    name: str
    description: str | None = None
    level: int
    is_active: bool
    user_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}