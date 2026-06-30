"""
Talentick — Content Service
==============================
CRUD محتوای سازمانی (Content) و آیتم‌های داخل آن (ContentItem).
هر query با org_id فیلتر می‌شود — Row-Level Security منطقی.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, ContentItem
from app.models.user import User
from app.schemas.content import (
    ContentCreate,
    ContentDetailResponse,
    ContentItemCreate,
    ContentItemResponse,
    ContentItemUpdate,
    ContentResponse,
    ContentUpdate,
)


# ─── Mappers ────────────────────────────────────────────────────────────────

def item_to_response(item: ContentItem) -> ContentItemResponse:
    return ContentItemResponse(
        id=str(item.id),
        content_id=str(item.content_id),
        title=item.title,
        type=item.type,
        body=item.body,
        media_url=item.media_url,
        quiz_id=str(item.quiz_id) if item.quiz_id else None,
        duration_min=item.duration_min,
        order_index=item.order_index,
        is_free=item.is_free,
        created_at=item.created_at,
    )


async def content_to_response(db: AsyncSession, content: Content) -> ContentResponse:
    created_by_name = None
    if content.created_by:
        creator = await db.get(User, content.created_by)
        created_by_name = creator.full_name if creator else None
    return ContentResponse(
        id=str(content.id),
        org_id=str(content.org_id),
        title=content.title,
        type=content.type,
        description=content.description,
        thumbnail_url=content.thumbnail_url,
        author=content.author,
        instructor_name=content.instructor_name,
        instructor_avatar_url=content.instructor_avatar_url,
        tags=content.tags or [],
        status=content.status,
        level=content.level,
        total_duration_min=content.total_duration_min,
        total_items_count=content.total_items_count,
        is_featured=content.is_featured,
        created_by=str(content.created_by) if content.created_by else None,
        created_by_name=created_by_name,
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


async def content_to_detail(db: AsyncSession, content: Content) -> ContentDetailResponse:
    base = await content_to_response(db, content)
    items_result = await db.execute(
        select(ContentItem)
        .where(ContentItem.content_id == content.id)
        .order_by(ContentItem.order_index)
    )
    items = [item_to_response(i) for i in items_result.scalars().all()]
    return ContentDetailResponse(**base.model_dump(), items=items)


# ─── Content CRUD ─────────────────────────────────────────────────────────

async def list_contents(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    type_filter: str | None = None,
    status_filter: str | None = None,
) -> tuple[list[Content], int]:
    q = select(Content).where(Content.org_id == org_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Content.title.ilike(like), Content.description.ilike(like)))
    if type_filter:
        q = q.where(Content.type == type_filter)
    if status_filter:
        q = q.where(Content.status == status_filter)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Content.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_content(db: AsyncSession, content_id: str) -> Content | None:
    try:
        cid = uuid.UUID(content_id)
    except ValueError:
        return None
    result = await db.execute(select(Content).where(Content.id == cid))
    return result.scalar_one_or_none()


async def create_content(
    db: AsyncSession, org_id: uuid.UUID, created_by: uuid.UUID, data: ContentCreate
) -> Content:
    content = Content(
        id=uuid.uuid4(),
        org_id=org_id,
        title=data.title,
        type=data.type,
        description=data.description,
        thumbnail_url=data.thumbnail_url,
        author=data.author,
        instructor_name=data.instructor_name,
        instructor_avatar_url=data.instructor_avatar_url,
        tags=data.tags,
        status=data.status,
        level=data.level,
        total_duration_min=data.total_duration_min,
        total_items_count=0,
        is_featured=data.is_featured,
        meta=data.meta,
        created_by=created_by,
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


async def update_content(db: AsyncSession, content: Content, data: ContentUpdate) -> Content:
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(content, field, value)
    await db.commit()
    await db.refresh(content)
    return content


async def delete_content(db: AsyncSession, content: Content) -> None:
    await db.delete(content)
    await db.commit()


async def _recount_items(db: AsyncSession, content_id: uuid.UUID) -> None:
    total = (
        await db.execute(
            select(func.count()).select_from(ContentItem).where(ContentItem.content_id == content_id)
        )
    ).scalar_one()
    content = await db.get(Content, content_id)
    if content:
        content.total_items_count = total
        await db.commit()


# ─── ContentItem CRUD ───────────────────────────────────────────────────────

async def add_item(
    db: AsyncSession, content: Content, data: ContentItemCreate
) -> ContentItem:
    item = ContentItem(
        id=uuid.uuid4(),
        org_id=content.org_id,
        content_id=content.id,
        title=data.title,
        type=data.type,
        body=data.body,
        media_url=data.media_url,
        quiz_id=uuid.UUID(data.quiz_id) if data.quiz_id else None,
        duration_min=data.duration_min,
        order_index=data.order_index,
        is_free=data.is_free,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    await _recount_items(db, content.id)
    return item


async def get_item(db: AsyncSession, item_id: str) -> ContentItem | None:
    try:
        iid = uuid.UUID(item_id)
    except ValueError:
        return None
    result = await db.execute(select(ContentItem).where(ContentItem.id == iid))
    return result.scalar_one_or_none()


async def update_item(db: AsyncSession, item: ContentItem, data: ContentItemUpdate) -> ContentItem:
    payload = data.model_dump(exclude_unset=True)
    if "quiz_id" in payload:
        payload["quiz_id"] = uuid.UUID(payload["quiz_id"]) if payload["quiz_id"] else None
    for field, value in payload.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, item: ContentItem) -> None:
    content_id = item.content_id
    await db.delete(item)
    await db.commit()
    await _recount_items(db, content_id)
