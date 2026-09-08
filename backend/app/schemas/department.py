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


class DepartmentMemberNode(BaseModel):
    """
    یک فرد داخل یک واحد سازمانی — برای نمایش تودرتوی افراد ذیل هر واحد
    در نمای درختیِ پنل ادمین (فقط وقتی `include_members=true` باشد).

    تودرتویی بر اساس «مدیر مستقیم» (`users.manager_id`) ساخته می‌شود و
    افرادِ هم‌رده بر اساس `position_level` نزولی و سپس نام مرتب می‌شوند.
    """
    id: str
    full_name: str
    avatar_url: str | None = None
    position_name: str | None = None
    position_level: int = 0
    is_manager: bool = False  # مدیرِ همین واحد
    is_active: bool = True
    children: list["DepartmentMemberNode"] = []


DepartmentMemberNode.model_rebuild()


class DepartmentTreeNode(BaseModel):
    """یک گره در چارت سازمانی — برای نمایش درختی در فرانت."""
    id: str
    name: str
    manager_name: str | None = None
    user_count: int = 0
    is_active: bool
    children: list["DepartmentTreeNode"] = []
    members: list[DepartmentMemberNode] = []


DepartmentTreeNode.model_rebuild()


class DepartmentReorderItem(BaseModel):
    """یک واحد با والد و ترتیب جدیدش — خروجی کشیدن‌ورهاکردن در نمای درختی."""
    id: str
    parent_id: str | None = None
    order_index: int = 0


class DepartmentReorderRequest(BaseModel):
    items: list[DepartmentReorderItem] = Field(..., min_length=1)
    # فقط super_admin مجاز است org_id غیر از سازمان خودش بدهد — در router enforce می‌شود
    org_id: str | None = None