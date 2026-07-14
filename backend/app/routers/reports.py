"""
Talentick — BI & Reporting Router
=====================================
گزارش‌های تحلیلی برای مدیران — قابل فیلتر بر اساس سازمان/واحد/پست/کاربر/
محتوا/بازه زمانی.

دسترسی: org_admin و بالاتر (به سازمان خودشان محدود)، super_admin به همه‌ی
سازمان‌ها (با امکان فیلتر با org_id، یا خالی = رول‌آپ کل پلتفرم).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin
from app.models.user import User
from app.schemas.reports import (
    ContentReportDetail,
    ContentReportRow,
    DashboardStats,
    OrganizationReportRow,
    UserReportRow,
)
from app.services import content_service, report_service

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID | None:
    if current_user.role == "super_admin":
        if org_id:
            try:
                return uuid.UUID(org_id)
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
        return None
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


@router.get("/dashboard", response_model=DashboardStats, summary="داشبورد آماری")
async def dashboard(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = کل پلتفرم"),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    stats = await report_service.dashboard_stats(db, target_org_id, date_from, date_to)
    return DashboardStats(**stats)


@router.get("/contents", response_model=list[ContentReportRow], summary="گزارش محتوا")
async def contents_report(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None),
    dept_id: str | None = Query(None),
    position_id: str | None = Query(None),
    user_id: str | None = Query(None),
    content_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    rows = await report_service.content_reports(
        db, target_org_id, dept_id=dept_id, position_id=position_id,
        user_id=user_id, content_id=content_id, date_from=date_from, date_to=date_to,
    )
    return [ContentReportRow(**r) for r in rows]


@router.get("/contents/{content_id}", response_model=ContentReportDetail, summary="گزارش تفصیلی یک محتوا")
async def content_report_detail(
    content_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    dept_id: str | None = Query(None),
    position_id: str | None = Query(None),
    user_id: str | None = Query(None),
):
    content = await content_service.get_content(db, content_id)
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    if current_user.role != "super_admin" and str(content.org_id) != str(current_user.org_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به این سازمان مجاز نیست")

    detail = await report_service.content_report_detail(
        db, content, dept_id=dept_id, position_id=position_id, user_id=user_id
    )
    return ContentReportDetail(
        content_id=str(content.id), title=content.title, type=content.type,
        status=content.status, users=detail["users"],
    )


@router.get("/organizations", response_model=list[OrganizationReportRow], summary="گزارش سازمان‌ها")
async def organizations_report(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    rows = await report_service.organization_reports(db, target_org_id)
    return [OrganizationReportRow(**r) for r in rows]


@router.get("/users", response_model=list[UserReportRow], summary="گزارش کاربران")
async def users_report(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None),
    dept_id: str | None = Query(None),
    position_id: str | None = Query(None),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    rows = await report_service.user_reports(db, target_org_id, dept_id=dept_id, position_id=position_id)
    return [UserReportRow(**r) for r in rows]
