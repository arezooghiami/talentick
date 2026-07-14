"""Talentick — BI & Reporting Schemas"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_contents: int
    active_contents: int
    total_eligible_users: int
    total_active_users: int
    started_count: int
    completed_count: int
    avg_progress_pct: int
    completion_rate: int
    total_view_time_seconds: int


class ContentReportRow(BaseModel):
    content_id: str
    title: str
    type: str
    status: str
    eligible_count: int
    viewed_count: int
    completed_count: int
    avg_progress_pct: int
    avg_view_time_seconds: int


class ContentReportUserRow(BaseModel):
    user_id: str
    full_name: str
    email: str
    department: Optional[str] = None
    position: Optional[str] = None
    status: str
    progress_pct: int
    view_time_seconds: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None


class ContentReportDetail(BaseModel):
    content_id: str
    title: str
    type: str
    status: str
    users: list[ContentReportUserRow]


class OrganizationReportRow(BaseModel):
    org_id: str
    org_name: str
    contents_count: int
    users_count: int
    viewed_count: int
    completed_count: int
    avg_progress_pct: int


class UserReportRow(BaseModel):
    user_id: str
    full_name: str
    email: str
    department: Optional[str] = None
    position: Optional[str] = None
    eligible_count: int
    started_count: int
    completed_count: int
    avg_progress_pct: int
    last_activity_at: Optional[datetime] = None
