"""
Talentick — Content Service
==============================
CRUD محتوای سازمانی (Content) و آیتم‌های داخل آن (ContentItem).
هر query با org_id فیلتر می‌شود — Row-Level Security منطقی.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import String as sa_String
from sqlalchemy import and_, cast as sa_cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import TARGET_TYPES, Content, ContentItem, ContentTarget
from app.models.organization import Department, Organization, Position
from app.models.user import User
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
    org = await db.get(Organization, content.org_id)
    target_count = (await db.execute(
        select(func.count()).select_from(ContentTarget).where(ContentTarget.content_id == content.id)
    )).scalar_one()
    return ContentResponse(
        id=str(content.id),
        org_id=str(content.org_id),
        org_name=org.name if org else None,
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
        sequential_progress=content.sequential_progress,
        target_count=target_count,
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


async def _target_to_response(db: AsyncSession, target: ContentTarget) -> ContentTargetResponse:
    label = None
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
    شرط SQL — Permission Engine مرکزی — همه‌ی endpointها (لیست/جزئیات/گزارش)
    باید از همین تابع استفاده کنند تا منطق دسترسی یک‌جا و یکپارچه بماند.

    منطق نهایی:
        (Department AND Position) OR Explicit User

    یعنی:
    - user_match: اگر یک سطر target_type='user' با شناسه‌ی این viewer وجود
      داشته باشد → همیشه مجاز (صرف‌نظر از بقیه شروط).
    - در غیر این صورت باید scope_match برقرار باشد:
        - dept_ok  = هیچ سطر department‌ای برای محتوا نیست، یا viewer در
                     یکی از department‌های انتخاب‌شده است.
        - pos_ok   = هیچ سطر position‌ای برای محتوا نیست، یا viewer در
                     یکی از position‌های انتخاب‌شده است.
        - scope_match = dept_ok AND pos_ok
    - اگر هیچ department و هیچ positionـی ثبت نشده باشد → dept_ok=pos_ok=True
      یعنی «بدون محدودیت» (قابل مشاهده برای کل سازمان).
    """
    user_match = exists(
        select(ContentTarget.id).where(
            ContentTarget.content_id == Content.id,
            ContentTarget.target_type == "user",
            ContentTarget.target_value == str(viewer.id),
        )
    )

    has_dept_targets = exists(
        select(ContentTarget.id).where(
            ContentTarget.content_id == Content.id, ContentTarget.target_type == "department"
        )
    )
    if viewer.dept_id:
        dept_match = exists(
            select(ContentTarget.id).where(
                ContentTarget.content_id == Content.id,
                ContentTarget.target_type == "department",
                ContentTarget.target_value == str(viewer.dept_id),
            )
        )
        dept_ok = or_(~has_dept_targets, dept_match)
    else:
        # کاربر بدون department ثبت‌شده — فقط زمانی مجاز است که هیچ محدودیت department‌ای وجود نداشته باشد
        dept_ok = ~has_dept_targets

    has_position_targets = exists(
        select(ContentTarget.id).where(
            ContentTarget.content_id == Content.id, ContentTarget.target_type == "position"
        )
    )
    if viewer.position_id:
        position_match = exists(
            select(ContentTarget.id).where(
                ContentTarget.content_id == Content.id,
                ContentTarget.target_type == "position",
                ContentTarget.target_value == str(viewer.position_id),
            )
        )
        position_ok = or_(~has_position_targets, position_match)
    else:
        position_ok = ~has_position_targets

    scope_match = and_(dept_ok, position_ok)
    return or_(scope_match, user_match)


async def eligible_user_ids_for_content(db: AsyncSession, content: Content) -> list[uuid.UUID]:
    """
    لیست شناسه‌ی همه‌ی کارمندان سازمان که مطابق Permission Engine مجاز به
    دیدن این محتوا هستند — برای گزارش‌گیری BI («تعداد کاربران مجاز»).

    همان منطق visibility_condition (Department AND Position) OR Explicit
    User را روی همه‌ی کارمندان سازمان اعمال می‌کند.
    """
    targets_result = await db.execute(
        select(ContentTarget).where(ContentTarget.content_id == content.id)
    )
    targets = list(targets_result.scalars().all())
    dept_ids = {t.target_value for t in targets if t.target_type == "department"}
    pos_ids = {t.target_value for t in targets if t.target_type == "position"}
    user_ids = {t.target_value for t in targets if t.target_type == "user"}

    q = select(User.id).where(User.org_id == content.org_id, User.role == "employee")

    if dept_ids or pos_ids:
        scope_clauses = []
        if dept_ids:
            scope_clauses.append(sa_cast(User.dept_id, sa_String).in_(dept_ids))
        if pos_ids:
            scope_clauses.append(sa_cast(User.position_id, sa_String).in_(pos_ids))
        scope_match = and_(*scope_clauses)
        user_match = sa_cast(User.id, sa_String).in_(user_ids) if user_ids else False
        q = q.where(or_(scope_match, user_match))
    # اگر نه department/position و نه user ثبت نشده باشد → بدون محدودیت (همه‌ی کارمندان)
    # اگر فقط user ثبت شده باشد (بدون scope) → طبق منطق AND/OR، scope خالی یعنی
    # بدون محدودیت است، پس باز هم همه‌ی کارمندان واجد شرایط‌اند.

    result = await db.execute(q)
    return list(result.scalars().all())


async def eligible_user_ids_map_for_contents(
    db: AsyncSession, contents: list[Content]
) -> dict[uuid.UUID, set[uuid.UUID]]:
    """
    نسخه‌ی Batch‌شده‌ی eligible_user_ids_for_content — برای گزارش‌گیری روی
    چند محتوا هم‌زمان (dashboard/reports).

    به‌جای N کوئری جداگانه (یکی به ازای هر محتوا در یک حلقه — مشکل N+1
    که در ممیزی عملکرد گزارش شد)، تمام ContentTarget های محتواهای ورودی و
    تمام کارمندان سازمان(های) درگیر را در دو کوئری می‌خواند و eligibility
    هر محتوا را در حافظه (طبق همان منطق visibility_condition) محاسبه
    می‌کند. خروجی: نگاشت content_id → مجموعه‌ی user_id های مجاز.
    """
    if not contents:
        return {}

    content_ids = [c.id for c in contents]
    targets_result = await db.execute(
        select(ContentTarget).where(ContentTarget.content_id.in_(content_ids))
    )
    targets_by_content: dict[uuid.UUID, list[ContentTarget]] = {}
    for t in targets_result.scalars().all():
        targets_by_content.setdefault(t.content_id, []).append(t)

    org_ids = {c.org_id for c in contents}
    users_result = await db.execute(
        select(User.id, User.org_id, User.dept_id, User.position_id).where(
            User.org_id.in_(org_ids), User.role == "employee"
        )
    )
    users_by_org: dict[uuid.UUID, list[tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None]]] = {}
    for uid, org_id, dept_id, position_id in users_result.all():
        users_by_org.setdefault(org_id, []).append((uid, dept_id, position_id))

    result: dict[uuid.UUID, set[uuid.UUID]] = {}
    for content in contents:
        targets = targets_by_content.get(content.id, [])
        dept_ids = {t.target_value for t in targets if t.target_type == "department"}
        pos_ids = {t.target_value for t in targets if t.target_type == "position"}
        user_ids = {t.target_value for t in targets if t.target_type == "user"}

        eligible: set[uuid.UUID] = set()
        for uid, dept_id, position_id in users_by_org.get(content.org_id, []):
            if dept_ids or pos_ids:
                scope_match = True
                if dept_ids:
                    scope_match = scope_match and dept_id is not None and str(dept_id) in dept_ids
                if pos_ids:
                    scope_match = scope_match and position_id is not None and str(position_id) in pos_ids
                if scope_match or str(uid) in user_ids:
                    eligible.add(uid)
            else:
                # بدون محدودیت department/position → کل کارمندان سازمان مجازند
                eligible.add(uid)
        result[content.id] = eligible

    return result


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
    apply_visibility: bool = False,
) -> tuple[list[Content], int]:
    """
    لیست محتوا با فیلتر/جستجو/صفحه‌بندی/مرتب‌سازی.

    - org_id=None → همه سازمان‌ها (فقط برای super_admin در مدیریت کلی)
    - viewer داده شود و role او employee باشد (یا apply_visibility=True — برای
      endpointهای «محتواهای من») → علاوه بر status=published، فقط محتوایی که
      مطابق Permission Engine (department/position/user) برای او مجاز است
      نمایش داده می‌شود.
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
    if viewer is not None and (apply_visibility or viewer.role == "employee"):
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
        sequential_progress=data.sequential_progress,
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
