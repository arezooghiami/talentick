"""
Talentick — Department Schemas
=================================
ساختار سازمانی درختی (واحدها). هر Department می‌تواند parent_id داشته
باشد تا یک چارت سازمانی چندسطحی بسازد.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    parent_id: str | None = None
    manager_id: str | None = None
    order_index: int = 0
    # فقط super_admin مجاز است org_id غیر از سازمان خودش بدهد — در router enforce می‌شود
    org_id: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    parent_id: str | None = None
    manager_id: str | None = None
    order_index: int | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    parent_id: str | None = None
    manager_id: str | None = None
    manager_name: str | None = None
    order_index: int
    is_active: bool
    user_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class DepartmentTreeNode(BaseModel):
    """یک گره در چارت سازمانی — برای نمایش درختی در فرانت."""
    id: str
    name: str
    manager_name: str | None = None
    user_count: int = 0
    is_active: bool
    children: list["DepartmentTreeNode"] = []


DepartmentTreeNode.model_rebuild()