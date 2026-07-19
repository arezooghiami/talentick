"""
Talentick — Ticket Service
==============================
دسته‌بندی (سراسری) + تیکت + ترد پیام + مجوز دسترسی اضافه.

قانون دسترسی به تیکت‌های یک سازمان:
    org_admin (سازمان خودش) و super_admin (همه‌جا) همیشه دسترسی دارند.
    فراتر از این، فقط اگر یک TicketAccessGrant برای همان org_id و
    (grant_type=role و role=نقش کاربر) یا (grant_type=user و user_id=خود
    کاربر) وجود داشته باشد — این مستقل از واگذاری تک‌تیکتی است: دسترسی
    یعنی دیدن/پاسخ‌دادن به همه‌ی تیکت‌های آن سازمان.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.organization import Organization
from app.models.ticket import (
    GRANT_TYPES,
    GRANTABLE_ROLES,
    TICKET_STATUSES,
    Ticket,
    TicketAccessGrant,
    TicketCategory,
    TicketMessage,
)
from app.models.user import User
from app.schemas.ticket import (
    TicketAccessGrantCreate,
    TicketAccessGrantResponse,
    TicketCategoryCreate,
    TicketCategoryResponse,
    TicketCategoryUpdate,
    TicketCreate,
    TicketDetailResponse,
    TicketMessageResponse,
    TicketResponse,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Categories (سراسری — فقط super_admin) ─────────────────────────────────

async def list_categories(db: AsyncSession, *, active_only: bool = False) -> list[TicketCategory]:
    q = select(TicketCategory).order_by(TicketCategory.order_index, TicketCategory.name)
    if active_only:
        q = q.where(TicketCategory.is_active.is_(True))
    return list((await db.execute(q)).scalars().all())


async def get_category(db: AsyncSession, category_id: str) -> TicketCategory | None:
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        return None
    return await db.get(TicketCategory, cid)


async def create_category(db: AsyncSession, data: TicketCategoryCreate) -> TicketCategory:
    category = TicketCategory(
        id=uuid.uuid4(), name=data.name, order_index=data.order_index, is_active=data.is_active,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(db: AsyncSession, category: TicketCategory, data: TicketCategoryUpdate) -> TicketCategory:
    payload = data.model_dump(exclude_unset=True)
    for field in ("name", "order_index", "is_active"):
        if field in payload:
            setattr(category, field, payload[field])
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category: TicketCategory) -> None:
    await db.delete(category)
    await db.commit()


def category_to_response(category: TicketCategory) -> TicketCategoryResponse:
    return TicketCategoryResponse(
        id=str(category.id), name=category.name,
        order_index=category.order_index, is_active=category.is_active,
    )


# ─── Access Control ─────────────────────────────────────────────────────────

async def user_can_access_org_tickets(db: AsyncSession, user: User, org_id: uuid.UUID) -> bool:
    """آیا این کاربر مجاز به دیدن/پاسخ‌دادن به تیکت‌های این سازمان است؟"""
    if user.role == "super_admin":
        return True
    if user.role == "org_admin" and str(user.org_id) == str(org_id):
        return True

    grant = (await db.execute(
        select(TicketAccessGrant).where(
            TicketAccessGrant.org_id == org_id,
            (
                ((TicketAccessGrant.grant_type == "role") & (TicketAccessGrant.role == user.role))
                | ((TicketAccessGrant.grant_type == "user") & (TicketAccessGrant.user_id == user.id))
            ),
        ).limit(1)
    )).scalar_one_or_none()
    return grant is not None


def require_ticket_access(has_access: bool) -> None:
    if not has_access:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی به تیکت‌های این سازمان را ندارید")


# ─── Access Grants (فقط super_admin) ───────────────────────────────────────

async def list_grants(db: AsyncSession, org_id: uuid.UUID | None = None) -> list[TicketAccessGrant]:
    q = select(TicketAccessGrant).order_by(TicketAccessGrant.created_at.desc())
    if org_id is not None:
        q = q.where(TicketAccessGrant.org_id == org_id)
    return list((await db.execute(q)).scalars().all())


async def get_grant(db: AsyncSession, grant_id: str) -> TicketAccessGrant | None:
    try:
        gid = uuid.UUID(grant_id)
    except ValueError:
        return None
    return await db.get(TicketAccessGrant, gid)


async def create_grant(db: AsyncSession, data: TicketAccessGrantCreate, granted_by: uuid.UUID) -> TicketAccessGrant:
    try:
        org_uuid = uuid.UUID(data.org_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
    org = await db.get(Organization, org_uuid)
    if not org:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سازمان یافت نشد")

    if data.grant_type not in GRANT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نوع مجوز نامعتبر — مقادیر مجاز: {', '.join(GRANT_TYPES)}")

    role = None
    user_uuid = None
    if data.grant_type == "role":
        if not data.role or data.role not in GRANTABLE_ROLES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نقش نامعتبر — مقادیر مجاز: {', '.join(GRANTABLE_ROLES)}")
        role = data.role
    else:
        if not data.user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id الزامی است")
        try:
            user_uuid = uuid.UUID(data.user_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id نامعتبر است")
        target_user = await db.get(User, user_uuid)
        if not target_user or str(target_user.org_id) != str(org_uuid):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر یافت نشد یا متعلق به این سازمان نیست")

    existing = (await db.execute(
        select(TicketAccessGrant).where(
            TicketAccessGrant.org_id == org_uuid,
            TicketAccessGrant.grant_type == data.grant_type,
            TicketAccessGrant.role == role,
            TicketAccessGrant.user_id == user_uuid,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    grant = TicketAccessGrant(
        id=uuid.uuid4(), org_id=org_uuid, grant_type=data.grant_type,
        role=role, user_id=user_uuid, granted_by=granted_by,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant


async def delete_grant(db: AsyncSession, grant: TicketAccessGrant) -> None:
    await db.delete(grant)
    await db.commit()


async def grant_to_response(db: AsyncSession, grant: TicketAccessGrant) -> TicketAccessGrantResponse:
    org = await db.get(Organization, grant.org_id)
    target_user = await db.get(User, grant.user_id) if grant.user_id else None
    granter = await db.get(User, grant.granted_by) if grant.granted_by else None
    return TicketAccessGrantResponse(
        id=str(grant.id), org_id=str(grant.org_id), org_name=org.name if org else None,
        grant_type=grant.grant_type, role=grant.role,
        user_id=str(grant.user_id) if grant.user_id else None,
        user_name=target_user.full_name if target_user else None,
        granted_by=str(grant.granted_by) if grant.granted_by else None,
        granted_by_name=granter.full_name if granter else None,
        created_at=grant.created_at,
    )


# ─── Tickets ─────────────────────────────────────────────────────────────────

async def create_ticket(db: AsyncSession, org_id: uuid.UUID, creator: User, data: TicketCreate) -> Ticket:
    category_uuid = None
    if data.category_id:
        try:
            category_uuid = uuid.UUID(data.category_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "category_id نامعتبر است")
        category = await db.get(TicketCategory, category_uuid)
        if not category or not category.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته‌بندی انتخاب‌شده معتبر نیست")

    content_uuid = None
    if data.related_content_id:
        try:
            content_uuid = uuid.UUID(data.related_content_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "related_content_id نامعتبر است")
        content = await db.get(Content, content_uuid)
        if not content or str(content.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "محتوای انتخاب‌شده معتبر نیست")

    ticket = Ticket(
        id=uuid.uuid4(), org_id=org_id, created_by=creator.id,
        category_id=category_uuid, related_content_id=content_uuid,
        subject=data.subject, status="open",
    )
    db.add(ticket)
    await db.flush()

    db.add(TicketMessage(
        id=uuid.uuid4(), org_id=org_id, ticket_id=ticket.id, sender_id=creator.id, body=data.body,
    ))
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def get_ticket(db: AsyncSession, ticket_id: str) -> Ticket | None:
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        return None
    return await db.get(Ticket, tid)


async def list_tickets(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    status_filter: str | None = None,
    category_id: str | None = None,
    search: str | None = None,
    created_by: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Ticket], int]:
    q = select(Ticket)
    if org_id is not None:
        q = q.where(Ticket.org_id == org_id)
    if status_filter:
        q = q.where(Ticket.status == status_filter)
    if category_id:
        try:
            q = q.where(Ticket.category_id == uuid.UUID(category_id))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "category_id نامعتبر است")
    if created_by is not None:
        q = q.where(Ticket.created_by == created_by)
    if search:
        q = q.where(Ticket.subject.ilike(f"%{search.strip()}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Ticket.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def add_message(db: AsyncSession, ticket: Ticket, sender: User, body: str, *, is_staff_reply: bool) -> TicketMessage:
    if ticket.status == "closed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این تیکت بسته شده — ابتدا آن را دوباره باز کنید")

    message = TicketMessage(
        id=uuid.uuid4(), org_id=ticket.org_id, ticket_id=ticket.id, sender_id=sender.id, body=body,
    )
    db.add(message)
    if is_staff_reply and ticket.status == "open":
        ticket.status = "answered"
    await db.commit()
    await db.refresh(message)
    return message


async def close_by_staff(db: AsyncSession, ticket: Ticket) -> Ticket:
    if ticket.status == "closed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این تیکت از قبل بسته شده است")
    ticket.status = "closed"
    ticket.closed_at = _now()
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def close_by_creator(db: AsyncSession, ticket: Ticket, rating: int) -> Ticket:
    if ticket.status == "closed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این تیکت از قبل بسته شده است")
    ticket.status = "closed"
    ticket.closed_at = _now()
    ticket.satisfaction_rating = rating
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def reopen_ticket(db: AsyncSession, ticket: Ticket) -> Ticket:
    if ticket.status != "closed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط تیکت بسته‌شده را می‌توان دوباره باز کرد")
    ticket.status = "open"
    ticket.closed_at = None
    ticket.satisfaction_rating = None
    await db.commit()
    await db.refresh(ticket)
    return ticket


# ─── Mappers ────────────────────────────────────────────────────────────────

async def message_to_response(db: AsyncSession, message: TicketMessage) -> TicketMessageResponse:
    sender = await db.get(User, message.sender_id) if message.sender_id else None
    return TicketMessageResponse(
        id=str(message.id),
        sender_id=str(message.sender_id) if message.sender_id else None,
        sender_name=sender.full_name if sender else None,
        sender_role=sender.role if sender else None,
        body=message.body,
        created_at=message.created_at,
    )


async def ticket_to_response(db: AsyncSession, ticket: Ticket) -> TicketResponse:
    org = await db.get(Organization, ticket.org_id)
    creator = await db.get(User, ticket.created_by)
    category = await db.get(TicketCategory, ticket.category_id) if ticket.category_id else None
    content = await db.get(Content, ticket.related_content_id) if ticket.related_content_id else None

    msg_stats = (await db.execute(
        select(func.count(), func.max(TicketMessage.created_at)).where(TicketMessage.ticket_id == ticket.id)
    )).one()
    message_count, last_message_at = msg_stats

    return TicketResponse(
        id=str(ticket.id), org_id=str(ticket.org_id), org_name=org.name if org else None,
        created_by=str(ticket.created_by), created_by_name=creator.full_name if creator else None,
        category_id=str(ticket.category_id) if ticket.category_id else None,
        category_name=category.name if category else None,
        related_content_id=str(ticket.related_content_id) if ticket.related_content_id else None,
        related_content_title=content.title if content else None,
        subject=ticket.subject, status=ticket.status,
        satisfaction_rating=ticket.satisfaction_rating, closed_at=ticket.closed_at,
        message_count=message_count or 0, last_message_at=last_message_at,
        created_at=ticket.created_at, updated_at=ticket.updated_at,
    )


async def ticket_to_detail(db: AsyncSession, ticket: Ticket) -> TicketDetailResponse:
    base = await ticket_to_response(db, ticket)
    messages_result = await db.execute(
        select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at)
    )
    messages = [await message_to_response(db, m) for m in messages_result.scalars().all()]
    return TicketDetailResponse(**base.model_dump(), messages=messages)
