"""
Talentick — Organization Schemas
"""
import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    name_en: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    values: Optional[str] = None
    culture: Optional[str] = None
    history: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    employee_count: Optional[int] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    values: Optional[str] = None
    culture: Optional[str] = None
    history: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    employee_count: Optional[int] = None
    is_active: Optional[bool] = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    name_en: Optional[str]
    logo_url: Optional[str] = None
    description: Optional[str]
    mission: Optional[str]
    vision: Optional[str]
    values: Optional[str] = None
    culture: Optional[str] = None
    history: Optional[str] = None
    website: Optional[str]
    phone: Optional[str]
    address: Optional[str] = None
    employee_count: Optional[int] = None
    plan: str
    is_active: bool
    created_at: Optional[datetime] = None   # ← اضافه شد

    model_config = {"from_attributes": True}
