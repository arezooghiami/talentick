"""
Talentick — Progress Service
===============================
ثبت پیشرفت کاربر در هر آیتم محتوا (UserItemProgress) و محاسبه‌ی خودکار
پیشرفت کل محتوا (UserContentProgress) از روی مجموع آیتم‌ها.

منطق تکمیل دوره: یک محتوا فقط وقتی completed است که تمام آیتم‌های آن
(۱۰۰٪) توسط کاربر تکمیل شده باشند — نه صرفاً میانگین درصد.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, ContentItem, UserContentProgress, UserItemProgress
from app.models.user import User
from app.schemas.progress import ContentProgressResponse, ItemProgressResponse, ItemProgressUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def item_progress_to_response(p: UserItemProgress) -> ItemProgressResponse:
    return ItemProgressResponse(
        item_id=str(p.item_id),
        status=p.status,
        progress_pct=p.progress_pct,
        last_position=p.last_position,
        view_time_seconds=p.view_time_seconds,
        started_at=p.started_at,
        completed_at=p.completed_at,
        last_viewed_at=p.last_viewed_at,
    )


def content_progress_to_response(p: UserContentProgress) -> ContentProgressResponse:
    return ContentProgressResponse(
        content_id=str(p.content_id),
        status=p.status,
        progress_pct=p.progress_pct,
        completed_items=p.completed_items,
        total_items=p.total_items,
        total_view_time_seconds=p.total_view_time_seconds,
        last_item_id=str(p.last_item_id) if p.last_item_id else None,
        started_at=p.started_at,
        completed_at=p.completed_at,
        last_viewed_at=p.last_viewed_at,
    )


async def get_content_progress(
    db: AsyncSession, user_id: uuid.UUID, content_id: uuid.UUID
) -> UserContentProgress | None:
    result = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.user_id == user_id, UserContentProgress.content_id == content_id
        )
    )
    return result.scalar_one_or_none()


async def get_item_progress_map(
    db: AsyncSession, user_id: uuid.UUID, content_id: uuid.UUID
) -> dict[str, UserItemProgress]:
    """نگاشت item_id → UserItemProgress برای یک کاربر در یک محتوا — برای نمایش وضعیت هر آیتم."""
    result = await db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id, UserItemProgress.content_id == content_id
        )
    )
    return {str(p.item_id): p for p in result.scalars().all()}


async def get_content_progress_map(
    db: AsyncSession, user_id: uuid.UUID, content_ids: list[uuid.UUID]
) -> dict[str, UserContentProgress]:
    """نگاشت content_id → UserContentProgress — برای نمایش کارت‌های «محتواهای من»."""
    if not content_ids:
        return {}
    result = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.user_id == user_id, UserContentProgress.content_id.in_(content_ids)
        )
    )
    return {str(p.content_id): p for p in result.scalars().all()}


async def start_content(db: AsyncSession, user: User, content: Content) -> UserContentProgress:
    """اولین بار که کاربر محتوا را باز می‌کند — سطر پیشرفت را می‌سازد یا برمی‌گرداند."""
    progress = await get_content_progress(db, user.id, content.id)
    if progress:
        if progress.status == "not_started":
            progress.status = "in_progress"
        progress.last_viewed_at = _now()
        await db.commit()
        await db.refresh(progress)
        return progress

    progress = UserContentProgress(
        id=uuid.uuid4(),
        org_id=content.org_id,
        user_id=user.id,
        content_id=content.id,
        total_items=content.total_items_count,
        completed_items=0,
        progress_pct=0,
        status="in_progress" if content.total_items_count else "not_started",
        started_at=_now(),
        last_viewed_at=_now(),
    )
    db.add(progress)
    await db.commit()
    await db.refresh(progress)
    return progress


async def update_item_progress(
    db: AsyncSession, user: User, content: Content, item: ContentItem, data: ItemProgressUpdate
) -> tuple[UserItemProgress, UserContentProgress]:
    """
    پیشرفت یک آیتم را به‌روزرسانی می‌کند و پیشرفت کل محتوا را از روی
    مجموع همه‌ی آیتم‌ها بازمحاسبه می‌کند.
    """
    result = await db.execute(
        select(UserItemProgress).where(UserItemProgress.user_id == user.id, UserItemProgress.item_id == item.id)
    )
    item_progress = result.scalar_one_or_none()
    now = _now()

    if not item_progress:
        item_progress = UserItemProgress(
            id=uuid.uuid4(),
            org_id=content.org_id,
            user_id=user.id,
            content_id=content.id,
            item_id=item.id,
            status="not_started",
            progress_pct=0,
            view_time_seconds=0,
            started_at=now,
        )
        db.add(item_progress)

    item_progress.progress_pct = max(item_progress.progress_pct, data.progress_pct)
    if data.position is not None:
        item_progress.last_position = data.position
    if data.view_time_seconds:
        item_progress.view_time_seconds += data.view_time_seconds
    item_progress.last_viewed_at = now
    if item_progress.started_at is None:
        item_progress.started_at = now

    if item_progress.progress_pct >= 100:
        item_progress.status = "completed"
        item_progress.progress_pct = 100
        if item_progress.completed_at is None:
            item_progress.completed_at = now
    elif item_progress.progress_pct > 0:
        item_progress.status = "in_progress"

    await db.flush()

    content_progress = await _recalculate_content_progress(db, user, content, last_item_id=item.id)
    await db.commit()
    await db.refresh(item_progress)
    await db.refresh(content_progress)
    return item_progress, content_progress


async def _recalculate_content_progress(
    db: AsyncSession, user: User, content: Content, last_item_id: uuid.UUID | None = None
) -> UserContentProgress:
    """
    پیشرفت کل محتوا را از روی مجموع آیتم‌های آن بازمحاسبه می‌کند.

    - progress_pct = میانگین progress_pct همه‌ی آیتم‌ها (آیتم‌های بدون سطر پیشرفت = ۰)
    - completed_items = تعداد آیتم‌هایی که status=='completed'
    - status: 'completed' فقط اگر همه‌ی آیتم‌ها (۱۰۰٪) تکمیل شده باشند،
      وگرنه 'in_progress' اگر حداقل یک آیتم شروع شده باشد، وگرنه 'not_started'.
    """
    total_items_result = await db.execute(
        select(func.count()).select_from(ContentItem).where(ContentItem.content_id == content.id)
    )
    total_items = total_items_result.scalar_one()

    agg_result = await db.execute(
        select(
            func.count(UserItemProgress.id),
            func.coalesce(func.sum(UserItemProgress.progress_pct), 0),
            func.count().filter(UserItemProgress.status == "completed"),
            func.coalesce(func.sum(UserItemProgress.view_time_seconds), 0),
        ).where(UserItemProgress.user_id == user.id, UserItemProgress.content_id == content.id)
    )
    touched_items, pct_sum, completed_items, total_view_time = agg_result.one()

    progress_pct = int(round(pct_sum / total_items)) if total_items else 0
    progress_pct = min(progress_pct, 100)

    if total_items and completed_items >= total_items:
        status = "completed"
        progress_pct = 100
    elif touched_items > 0:
        status = "in_progress"
    else:
        status = "not_started"

    content_progress = await get_content_progress(db, user.id, content.id)
    now = _now()
    if not content_progress:
        content_progress = UserContentProgress(
            id=uuid.uuid4(),
            org_id=content.org_id,
            user_id=user.id,
            content_id=content.id,
            started_at=now,
        )
        db.add(content_progress)

    content_progress.total_items = total_items
    content_progress.completed_items = completed_items
    content_progress.progress_pct = progress_pct
    content_progress.status = status
    content_progress.total_view_time_seconds = total_view_time
    content_progress.last_viewed_at = now
    if last_item_id is not None:
        content_progress.last_item_id = last_item_id
    if content_progress.started_at is None:
        content_progress.started_at = now
    if status == "completed" and content_progress.completed_at is None:
        content_progress.completed_at = now
    elif status != "completed":
        content_progress.completed_at = None

    await db.flush()
    return content_progress
