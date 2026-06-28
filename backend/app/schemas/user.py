"""
Talentick — User Schemas
"""
import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr


VALID_ROLES = {"super_admin", "org_admin", "manager", "employee"}


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "employee"
    org_id: uuid.UUID
    phone: Optional[str] = None

    def model_post_init(self, __context):
        if self.role not in VALID_ROLES:
            raise ValueError(f"نقش نامعتبر: {self.role}")


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    full_name: str
    role: str
    phone: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}