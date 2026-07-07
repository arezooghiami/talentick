"""
Talentick — Content Service
==============================
CRUD محتوای سازمانی (Content) و آیتم‌های داخل آن (ContentItem).
هر query با org_id فیلتر می‌شود — Row-Level Security منطقی.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import TARGET_TYPES, Content, ContentItem, ContentTarget
from app.models.organization import Department, Position
from app.models.user import VALID_ROLES, User
from app.schemas.content import (
    ContentCreate,
    ContentDetailResponse,
    ContentItemCreate,
    ContentItemResponse,
    ContentItemUpdate,
    ContentResponse,
    ContentTargetCreate,
    ContentTargetResponse,
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

    targets_result = await db.execute(
        select(ContentTarget).where(ContentTarget.content_id == content.id)
    )
    targets = [await _target_to_response(db, t) for t in targets_result.scalars().all()]

    return ContentDetailResponse(**base.model_dump(), items=items, targets=targets)


# ─── Targeting (انتشار هدفمند: دپارتمان/پست/نقش/کاربر) ─────────────────────

async def _validate_targets(
    db: AsyncSession, org_id: uuid.UUID, targets: list[ContentTargetCreate]
) -> None:
    """هر هدف باید نوع معتبر داشته باشد و به همان سازمان تعلق داشته باشد."""
    for t in targets:
        if t.target_type not in TARGET_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"نوع هدف نامعتبر است — مقادیر مجاز: {', '.join(TARGET_TYPES)}",
            )
        if t.target_type == "role":
            if t.target_id not in VALID_ROLES:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "نقش انتخاب‌شده معتبر نیست")
            continue
        try:
            target_uuid = uuid.UUID(t.target_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه هدف نامعتبر است")

        if t.target_type == "department":
            dept = await db.get(Department, target_uuid)
            if not dept or str(dept.org_id) != str(org_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "دپارتمان انتخاب‌شده معتبر نیست")
        elif t.target_type == "position":
            pos = await db.get(Position, target_uuid)
            if not pos or str(pos.org_id) != str(org_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "پست انتخاب‌شده معتبر نیست")
        elif t.target_type == "user":
            user = await db.get(User, target_uuid)
            if not user or str(user.org_id) != str(org_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر انتخاب‌شده معتبر نیست")


ROLE_LABELS = {
    "super_admin": "سوپرادمین",
    "org_admin": "مدیر سازمان",
    "manager": "مدیر واحد",
    "employee": "کارمند",
}


async def _target_to_response(db: AsyncSession, target: ContentTarget) -> ContentTargetResponse:
    label = None
    if target.target_type == "role":
        label = ROLE_LABELS.get(target.target_value, target.target_value)
    else:
        try:
            target_uuid = uuid.UUID(target.target_value)
        except ValueError:
            target_uuid = None
        if target_uuid:
            if target.target_type == "department":
                dept = await db.get(Department, target_uuid)
                label = dept.name if dept else None
            elif target.target_type == "position":
                pos = await db.get(Position, target_uuid)
                label = pos.name if pos else None
            elif target.target_type == "user":
                user = await db.get(User, target_uuid)
                label = user.full_name if user else None
    return ContentTargetResponse(
        id=str(target.id),
        target_type=target.target_type,
        target_id=target.target_value,
        target_label=label,
    )


async def _create_targets(
    db: AsyncSession, org_id: uuid.UUID, content_id: uuid.UUID, targets: list[ContentTargetCreate]
) -> None:
    seen: set[tuple[str, str]] = set()
    for t in targets:
        key = (t.target_type, t.target_id)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            ContentTarget(
                id=uuid.uuid4(),
                org_id=org_id,
                content_id=content_id,
                target_type=t.target_type,
                target_value=t.target_id,
            )
        )


async def replace_targets(
    db: AsyncSession, content: Content, targets: list[ContentTargetCreate]
) -> None:
    """تمام هدف‌های قبلی محتوا را پاک و هدف‌های جدید را جایگزین می‌کند."""
    await _validate_targets(db, content.org_id, targets)
    await db.execute(
        ContentTarget.__table__.delete().where(ContentTarget.content_id == content.id)
    )
    await _create_targets(db, content.org_id, content.id, targets)
    await db.commit()


async def is_visible_to_user(db: AsyncSession, content: Content, viewer: User) -> bool:
    """آیا این محتوای مشخص برای این کاربر (employee) قابل مشاهده است؟"""
    q = select(Content.id).where(Content.id == content.id, visibility_condition(viewer))
    result = await db.execute(q)
    return result.scalar_one_or_none() is not None


def visibility_condition(viewer: User):
    """
    شرط SQL برای فیلتر محتوایی که یک کارمند مجاز به دیدن آن است:
    - محتوایی که هیچ هدفی برایش تعریف نشده (برای کل سازمان) یا
    - محتوایی که حداقل یکی از هدف‌هایش با دپارتمان/پست/نقش/شناسه کاربر او match می‌شود.

    فقط برای نقش employee استفاده می‌شود — manager به بالا همه محتوای
    سازمان را برای مدیریت می‌بینند.
    """
    match_clauses = [
        and_(ContentTarget.target_type == "role", ContentTarget.target_value == viewer.role),
        and_(ContentTarget.target_type == "user", ContentTarget.target_value == str(viewer.id)),
    ]
    if viewer.dept_id:
        match_clauses.append(
            and_(ContentTarget.target_type == "department", ContentTarget.target_value == str(viewer.dept_id))
        )
    if viewer.position_id:
        match_clauses.append(
            and_(ContentTarget.target_type == "position", ContentTarget.target_value == str(viewer.position_id))
        )

    has_targets = exists(
        select(ContentTarget.id).where(ContentTarget.content_id == Content.id)
    )
    matches_target = exists(
        select(ContentTarget.id).where(
            ContentTarget.content_id == Content.id, or_(*match_clauses)
        )
    )
    return or_(~has_targets, matches_target)


# ─── Content CRUD ─────────────────────────────────────────────────────────

_SORTABLE_FIELDS = {
    "created_at": Content.created_at,
    "updated_at": Content.updated_at,
    "title": Content.title,
    "status": Content.status,
    "type": Content.type,
}


async def list_contents(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    type_filter: str | None = None,
    status_filter: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    viewer: User | None = None,
) -> tuple[list[Content], int]:
    """
    لیست محتوا با فیلتر/جستجو/صفحه‌بندی/مرتب‌سازی.

    - org_id=None → همه سازمان‌ها (فقط برای super_admin در مدیریت کلی)
    - viewer داده شود و role او employee باشد → علاوه بر status=published،
      فقط محتوایی که مطابق دپارتمان/پست/نقش/شناسه‌ی خودش هدف‌گذاری شده
      (یا اصلاً هدف‌گذاری نشده) نمایش داده می‌شود.
    """
    q = select(Content)
    if org_id is not None:
        q = q.where(Content.org_id == org_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Content.title.ilike(like), Content.description.ilike(like)))
    if type_filter:
        q = q.where(Content.type == type_filter)
    if status_filter:
        q = q.where(Content.status == status_filter)
    if viewer is not None and viewer.role == "employee":
        q = q.where(visibility_condition(viewer))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    sort_col = _SORTABLE_FIELDS.get(sort_by, Content.created_at)
    sort_col = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    q = q.order_by(sort_col).offset((page - 1) * page_size).limit(page_size)
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
    if data.targets:
        await _validate_targets(db, org_id, data.targets)

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
    await db.flush()

    if data.targets:
        await _create_targets(db, org_id, content.id, data.targets)

    await db.commit()
    await db.refresh(content)
    return content


async def update_content(db: AsyncSession, content: Content, data: ContentUpdate) -> Content:
    payload = data.model_dump(exclude_unset=True, exclude={"targets"})
    for field, value in payload.items():
        setattr(content, field, value)
    await db.commit()
    await db.refresh(content)

    if data.targets is not None:
        await replace_targets(db, content, data.targets)

    return content


async def set_cover(db: AsyncSession, content: Content, thumbnail_url: str | None) -> Content:
    """کاور محتوا را تنظیم یا پاک می‌کند (thumbnail_url=None یعنی حذف کاور)."""
    content.thumbnail_url = thumbnail_url
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
