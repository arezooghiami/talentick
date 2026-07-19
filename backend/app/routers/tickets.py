"""
Talentick — Ticket Router (Admin/Staff Side)
================================================
دیدن/پاسخ‌دادن به تیکت‌ها (org_admin سازمان خودش + super_admin همه‌جا +
هر کسی که super_admin با TicketAccessGrant به او دسترسی داده) + مدیریت
دسته‌بندی‌ها و مجوزهای دسترسی (فقط super_admin).

Routes:
  GET    /api/ticket-categories                → لیست دسته‌بندی‌ها (هر کاربر فعال)
  POST   /api/ticket-categories                → ساخت دسته‌بندی (super_admin)
  PATCH  /api/ticket-categories/{id}            → ویرایش دسته‌بندی (super_admin)
  DELETE /api/ticket-categories/{id}            → حذف دسته‌بندی (super_admin)

  GET    /api/tickets                           → لیست تیکت‌ها (مدیریتی)
  GET    /api/tickets/{id}                      → جزئیات + ترد پیام‌ها
  POST   /api/tickets/{id}/messages             → پاسخ ادمین/مسئول
  POST   /api/tickets/{id}/close                → بستن اجباری (بدون امتیاز — مثلاً اسپم)

  GET    /api/tickets/access-grants             → لیست مجوزهای دسترسی (super_admin)
  POST   /api/tickets/access-grants             → افزودن مجوز (super_admin)
  DELETE /api/tickets/access-grants/{id}         → حذف مجوز (super_admin)

ثبت تیکت/پاسخ/بستن به‌عنوان کارمند از routers/me.py (POST /api/me/tickets و ...) است.
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import ActiveUser, SuperAdmin
from app.models.user import User
from app.schemas.ticket import (
    TicketAccessGrantCreate,
    TicketAccessGrantResponse,
    TicketCategoryCreate,
    TicketCategoryResponse,
    TicketCategoryUpdate,
    TicketDetailResponse,
    TicketListResponse,
    TicketMessageCreate,
    TicketMessageResponse,
)
from app.services import ticket_service

router = APIRouter(prefix="/api", tags=["Tickets"])


async def _resolve_staff_org_scope(
    db: AsyncSession, current_user: User, org_id: str | None
) -> uuid.UUID | None:
    """super_admin: org_id اختیاری (خالی = همه‌ی سازمان‌ها). بقیه: همیشه سازمان خودشان + بررسی مجوز دسترسی."""
    if current_user.role == "super_admin":
        if org_id:
            try:
                return uuid.UUID(org_id)
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
        return None
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    has_access = await ticket_service.user_can_access_org_tickets(db, current_user, current_user.org_id)
    ticket_service.require_ticket_access(has_access)
    return current_user.org_id


async def _get_ticket_with_access(db: AsyncSession, current_user: User, ticket_id: str):
    ticket = await ticket_service.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تیکت یافت نشد")
    has_access = await ticket_service.user_can_access_org_tickets(db, current_user, ticket.org_id)
    ticket_service.require_ticket_access(has_access)
    return ticket


# ─── Categories ───────────────────────────────────────────────────────────

@router.get("/ticket-categories", response_model=list[TicketCategoryResponse], summary="لیست دسته‌بندی‌های تیکت")
async def list_categories(
    current_user: ActiveUser,
    db: AsyncSession = Depends(get_db),
    active_only: bool = Query(True),
):
    categories = await ticket_service.list_categories(db, active_only=active_only)
    return [ticket_service.category_to_response(c) for c in categories]


@router.post(
    "/ticket-categories", response_model=TicketCategoryResponse, status_code=status.HTTP_201_CREATED,
    summary="ساخت دسته‌بندی جدید (super_admin)",
)
async def create_category(
    body: TicketCategoryCreate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    category = await ticket_service.create_category(db, body)
    return ticket_service.category_to_response(category)


@router.patch("/ticket-categories/{category_id}", response_model=TicketCategoryResponse, summary="ویرایش دسته‌بندی (super_admin)")
async def update_category(
    category_id: str,
    body: TicketCategoryUpdate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    category = await ticket_service.get_category(db, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌بندی یافت نشد")
    updated = await ticket_service.update_category(db, category, body)
    return ticket_service.category_to_response(updated)


@router.delete("/ticket-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف دسته‌بندی (super_admin)")
async def delete_category(
    category_id: str,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    category = await ticket_service.get_category(db, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌بندی یافت نشد")
    await ticket_service.delete_category(db, category)


# ─── Access Grants ────────────────────────────────────────────────────────

@router.get("/tickets/access-grants", response_model=list[TicketAccessGrantResponse], summary="لیست مجوزهای دسترسی (super_admin)")
async def list_access_grants(
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None),
):
    org_uuid = None
    if org_id:
        try:
            org_uuid = uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
    grants = await ticket_service.list_grants(db, org_uuid)
    return [await ticket_service.grant_to_response(db, g) for g in grants]


@router.post(
    "/tickets/access-grants", response_model=TicketAccessGrantResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن مجوز دسترسی به نقش/کاربر خاص (super_admin)",
)
async def create_access_grant(
    body: TicketAccessGrantCreate,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    grant = await ticket_service.create_grant(db, body, granted_by=current_user.id)
    return await ticket_service.grant_to_response(db, grant)


@router.delete("/tickets/access-grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف مجوز دسترسی (super_admin)")
async def delete_access_grant(
    grant_id: str,
    current_user: SuperAdmin,
    db: AsyncSession = Depends(get_db),
):
    grant = await ticket_service.get_grant(db, grant_id)
    if not grant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مجوز یافت نشد")
    await ticket_service.delete_grant(db, grant)


# ─── Tickets ──────────────────────────────────────────────────────────────

@router.get("/tickets", response_model=TicketListResponse, summary="لیست تیکت‌ها (مدیریتی)")
async def list_tickets(
    current_user: ActiveUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    category_id: str | None = Query(None),
    search: str | None = Query(None),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = همه سازمان‌ها"),
):
    target_org_id = await _resolve_staff_org_scope(db, current_user, org_id)
    items, total = await ticket_service.list_tickets(
        db, target_org_id, status_filter=status_filter, category_id=category_id,
        search=search, page=page, page_size=page_size,
    )
    responses = [await ticket_service.ticket_to_response(db, t) for t in items]
    return TicketListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse, summary="جزئیات تیکت + ترد پیام‌ها")
async def get_ticket(
    ticket_id: str,
    current_user: ActiveUser,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_ticket_with_access(db, current_user, ticket_id)
    return await ticket_service.ticket_to_detail(db, ticket)


@router.post("/tickets/{ticket_id}/messages", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED, summary="پاسخ به تیکت")
async def reply_to_ticket(
    ticket_id: str,
    body: TicketMessageCreate,
    current_user: ActiveUser,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_ticket_with_access(db, current_user, ticket_id)
    message = await ticket_service.add_message(db, ticket, current_user, body.body, is_staff_reply=True)
    return await ticket_service.message_to_response(db, message)


@router.post("/tickets/{ticket_id}/close", response_model=TicketDetailResponse, summary="بستن اجباری تیکت (بدون امتیاز — مثلاً اسپم/تکراری)")
async def close_ticket(
    ticket_id: str,
    current_user: ActiveUser,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_ticket_with_access(db, current_user, ticket_id)
    await ticket_service.close_by_staff(db, ticket)
    return await ticket_service.ticket_to_detail(db, ticket)
