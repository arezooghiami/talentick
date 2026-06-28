"""
Talentick — Organization Schemas
"""
import uuid
from pydantic import BaseModel
from typing import Optional


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    name_en: Optional[str]
    description: Optional[str]
    mission: Optional[str]
    vision: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    plan: str
    is_active: bool

    model_config = {"from_attributes": True}