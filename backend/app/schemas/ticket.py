"""
Talentick — Ticket Schemas
=============================
تیکتینگ: TicketCategory (سراسری) → Ticket → TicketMessage (ترد) +
TicketAccessGrant (مجوز دسترسی اضافه‌ی super_admin به یک نقش/کاربر).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

TICKET_STATUSES = ("open", "answered", "closed")
GRANT_TYPES = ("role", "user")
GRANTABLE_ROLES = ("manager", "employee")


# ─── TicketCategory ────────────────────────────────────────────────────────

class TicketCategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    order_index: int = 0
    is_active: bool = True


class TicketCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    order_index: Optional[int] = None
    is_active: Optional[bool] = None


class TicketCategoryResponse(BaseModel):
    id: str
    name: str
    order_index: int
    is_active: bool

    model_config = {"from_attributes": True}


# ─── TicketMessage ─────────────────────────────────────────────────────────

class TicketMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=5000)


class TicketMessageResponse(BaseModel):
    id: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Ticket ────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=2, max_length=500)
    body: str = Field(..., min_length=1, max_length=5000, description="متن اولین پیام تیکت")
    category_id: Optional[str] = None
    related_content_id: Optional[str] = None


class TicketCloseRequest(BaseModel):
    satisfaction_rating: int = Field(..., ge=1, le=5)


class TicketResponse(BaseModel):
    id: str
    org_id: str
    org_name: Optional[str] = None
    created_by: str
    created_by_name: Optional[str] = None
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    related_content_id: Optional[str] = None
    related_content_title: Optional[str] = None
    subject: str
    status: str
    satisfaction_rating: Optional[int] = None
    closed_at: Optional[datetime] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketDetailResponse(TicketResponse):
    messages: list[TicketMessageResponse] = Field(default_factory=list)


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── TicketAccessGrant ─────────────────────────────────────────────────────

class TicketAccessGrantCreate(BaseModel):
    org_id: str
    grant_type: str = Field(..., description="role | user")
    role: Optional[str] = Field(None, description="فقط وقتی grant_type=role — manager | employee")
    user_id: Optional[str] = Field(None, description="فقط وقتی grant_type=user")


class TicketAccessGrantResponse(BaseModel):
    id: str
    org_id: str
    org_name: Optional[str] = None
    grant_type: str
    role: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    granted_by: Optional[str] = None
    granted_by_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
