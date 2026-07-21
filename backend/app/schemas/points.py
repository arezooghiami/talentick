"""
Talentick — Points (Gamification) Schemas
=============================================
PointRule (سراسری، Event Driven، مدیریت super_admin) + PointPolicyRule
(Priority Engine ۴سطحی: User/Position/Department/Organization) +
PointsLedgerEntry (دفترکل) + PointWallet (کیف‌پول).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class PointRuleResponse(BaseModel):
    id: str
    event_type: str
    event_label: str
    points: int
    is_active: bool

    model_config = {"from_attributes": True}


class PointRuleCreate(BaseModel):
    """ساخت یک نوع Event جدید — نظام Event Driven، بدون نیاز به تغییر کد."""
    event_type: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    event_label: str = Field(..., min_length=1, max_length=100)
    points: int = Field(0, ge=0, le=100000)
    is_active: bool = True


class PointRuleUpdate(BaseModel):
    event_label: Optional[str] = Field(None, min_length=1, max_length=100)
    points: Optional[int] = Field(None, ge=0, le=100000)
    is_active: Optional[bool] = None


# ─── Policy Rules (Priority Engine — User/Position/Department/Organization) ─

class PointPolicyRuleCreate(BaseModel):
    event_type: str = Field(..., min_length=2, max_length=50)
    org_id: Optional[str] = None
    dept_id: Optional[str] = None
    position_id: Optional[str] = None
    user_id: Optional[str] = None
    points: int = Field(..., ge=0, le=100000)
    priority: int = Field(0, description="تای‌بریک دستی وقتی چند Rule هم‌سطح صدق کنند — بزرگ‌تر برنده است")
    is_active: bool = True

    @model_validator(mode="after")
    def _at_least_one_scope(self) -> "PointPolicyRuleCreate":
        if not any([self.org_id, self.dept_id, self.position_id, self.user_id]):
            raise ValueError("حداقل یکی از سازمان/واحد/سمت/کاربر باید مشخص شود")
        return self


class PointPolicyRuleUpdate(BaseModel):
    points: Optional[int] = Field(None, ge=0, le=100000)
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class PointPolicyRuleResponse(BaseModel):
    id: str
    event_type: str
    event_label: str
    tier: str = Field(..., description="user | position | department | organization")
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    dept_id: Optional[str] = None
    dept_name: Optional[str] = None
    position_id: Optional[str] = None
    position_name: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    points: int
    priority: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Ledger + Wallet ─────────────────────────────────────────────────────────

class PointsLedgerEntryResponse(BaseModel):
    id: str
    transaction_number: str
    transaction_type: str
    event_type: str
    event_label: str
    reference_id: str
    reference_title: Optional[str] = None
    points: int
    balance_before: int
    balance_after: int
    points_source: Optional[str] = None
    description: Optional[str] = None
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PointsHistoryResponse(BaseModel):
    items: list[PointsLedgerEntryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PointsSummaryResponse(BaseModel):
    total_points: int


class WalletResponse(BaseModel):
    current_balance: int
    total_earned: int
    total_spent: int
    total_expired: int
    pending_points: int
    redeemed_points: int


class ManualTransactionCreate(BaseModel):
    user_id: str
    transaction_type: str = Field(..., description="bonus | manual_adjustment | deduction | correction")
    points: int = Field(..., description="برای deduction همیشه مثبت وارد شود (خودش منفی می‌شود)")
    description: str = Field(..., min_length=1, max_length=1000)
