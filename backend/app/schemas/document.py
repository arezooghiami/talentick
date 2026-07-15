"""
Talentick — Document Library Schemas
=======================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

DOCUMENT_TARGET_TYPES = ("department", "role")


# ─── DocumentCategory ───────────────────────────────────────────────────────

class DocumentCategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    order_index: int = 0


class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    order_index: Optional[int] = None


class DocumentCategoryResponse(BaseModel):
    id: str
    name: str
    order_index: int
    document_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── DocumentTarget (دسترسی: واحد/نقش) ──────────────────────────────────────

class DocumentTargetCreate(BaseModel):
    """
    یک بعد از قانون دسترسی سند.

    target_type=department → target_id باید dept_id باشد.
    target_type=role       → target_id باید یکی از super_admin|org_admin|manager|employee باشد.

    منطق نهایی (در document_service.visibility_condition): بدون هیچ
    target = برای کل سازمان. با وجود target، کافیست کاربر با یکی از
    سطرها مطابقت داشته باشد (OR).
    """
    target_type: str = Field(..., description="department | role")
    target_id: str = Field(..., min_length=1, description="UUID واحد یا نام نقش")


class DocumentTargetResponse(BaseModel):
    id: str
    target_type: str
    target_id: str
    target_label: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Document ────────────────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    category_id: Optional[str] = None
    file_url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    targets: list[DocumentTargetCreate] = Field(
        default_factory=list,
        description="قوانین دسترسی — خالی یعنی برای کل سازمان",
    )


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=500)
    description: Optional[str] = None
    category_id: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    targets: Optional[list[DocumentTargetCreate]] = Field(
        None,
        description="اگر ارسال شود، جایگزین همه‌ی قوانین قبلی می‌شود. [] یعنی پاک‌کردن (کل سازمان).",
    )


class DocumentResponse(BaseModel):
    id: str
    org_id: str
    title: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    file_url: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_by_name: Optional[str] = None
    target_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    targets: list[DocumentTargetResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
