"""
Talentick — BI & Reporting Service
=====================================
گزارش‌های تحلیلی روی محتوا/سازمان/کاربر — با استفاده از همان Permission
Engine مرکزی (content_service.eligible_user_ids_for_content) تا اعداد
«کاربران مجاز» همیشه با آنچه کاربر واقعاً می‌بیند یکی باشد.

توجه: برای سادگی و صحت در فاز اول، تجمیع بیشتر در سطح Python روی
مجموعه‌های نسبتاً کوچک (محتوای هر سازمان) انجام می‌شود؛ در فازهای بعدی
در صورت رشد داده می‌توان به SQL تجمیعی مهاجرت کرد.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, UserContentProgress
from app.models.organization import Department, Organization, Position
from app.models.user import User
from app.services import content_service


async def _published_contents(db: AsyncSession, org_id: uuid.UUID | None) -> list[Content]:
    q = select(Content).where(Content.status == "published")
    if org_id is not None:
        q = q.where(Content.org_id == org_id)
    return list((await db.execute(q)).scalars().all())


async def _progress_rows_for_contents(
    db: AsyncSession, content_ids: list[uuid.UUID]
) -> list[UserContentProgress]:
    if not content_ids:
        return []
    result = await db.execute(
        select(UserContentProgress).where(UserContentProgress.content_id.in_(content_ids))
    )
    return list(result.scalars().all())


def _in_range(dt: datetime | None, date_from: datetime | None, date_to: datetime | None) -> bool:
    if dt is None:
        return date_from is None and date_to is None
    if date_from and dt < date_from:
        return False
    if date_to and dt > date_to:
        return False
    return True


# ─── داشبورد مدیریتی ─────────────────────────────────────────────────────

async def dashboard_stats(
    db: AsyncSession, org_id: uuid.UUID | None, date_from: datetime | None, date_to: datetime | None
) -> dict:
    all_contents_q = select(Content)
    if org_id is not None:
        all_contents_q = all_contents_q.where(Content.org_id == org_id)
    all_contents = list((await db.execute(all_contents_q)).scalars().all())
    published = [c for c in all_contents if c.status == "published"]

    # Batch شده — یک کوئری برای همه‌ی محتواها به‌جای N کوئری در حلقه (رفع N+1)
    eligibility_map = await content_service.eligible_user_ids_map_for_contents(db, published)
    eligible_users: set[uuid.UUID] = set()
    for ids in eligibility_map.values():
        eligible_users.update(ids)

    active_users_q = select(User).where(User.role == "employee", User.is_active.is_(True))
    if org_id is not None:
        active_users_q = active_users_q.where(User.org_id == org_id)
    active_users = list((await db.execute(active_users_q)).scalars().all())

    progress_rows = await _progress_rows_for_contents(db, [c.id for c in published])
    progress_rows = [p for p in progress_rows if _in_range(p.last_viewed_at or p.started_at, date_from, date_to)]

    started = [p for p in progress_rows if p.status in ("in_progress", "completed")]
    completed = [p for p in progress_rows if p.status == "completed"]
    avg_progress = round(sum(p.progress_pct for p in progress_rows) / len(progress_rows)) if progress_rows else 0
    total_view_time = sum(p.total_view_time_seconds for p in progress_rows)
    completion_rate = round(len(completed) / len(started) * 100) if started else 0

    return {
        "total_contents": len(all_contents),
        "active_contents": len(published),
        "total_eligible_users": len(eligible_users),
        "total_active_users": len(active_users),
        "started_count": len(started),
        "completed_count": len(completed),
        "avg_progress_pct": avg_progress,
        "completion_rate": completion_rate,
        "total_view_time_seconds": total_view_time,
    }


# ─── گزارش محتوا ──────────────────────────────────────────────────────────

async def content_reports(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    dept_id: str | None = None,
    position_id: str | None = None,
    user_id: str | None = None,
    content_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict]:
    contents = await _published_contents(db, org_id)
    if content_id:
        contents = [c for c in contents if str(c.id) == content_id]

    # Batch شده — یک کوئری برای همه‌ی محتواها به‌جای N کوئری در حلقه (رفع N+1)
    eligibility_map = await content_service.eligible_user_ids_map_for_contents(db, contents)

    rows = []
    for c in contents:
        eligible_ids = set(eligibility_map.get(c.id, set()))
        if dept_id or position_id or user_id:
            filtered_users_q = select(User.id).where(User.id.in_(eligible_ids)) if eligible_ids else None
            if filtered_users_q is not None:
                if dept_id:
                    filtered_users_q = filtered_users_q.where(User.dept_id == uuid.UUID(dept_id))
                if position_id:
                    filtered_users_q = filtered_users_q.where(User.position_id == uuid.UUID(position_id))
                if user_id:
                    filtered_users_q = filtered_users_q.where(User.id == uuid.UUID(user_id))
                eligible_ids = set((await db.execute(filtered_users_q)).scalars().all())

        progress_result = await db.execute(
            select(UserContentProgress).where(
                UserContentProgress.content_id == c.id, UserContentProgress.user_id.in_(eligible_ids)
            )
        ) if eligible_ids else None
        progress_rows = list(progress_result.scalars().all()) if progress_result else []
        progress_rows = [p for p in progress_rows if _in_range(p.last_viewed_at or p.started_at, date_from, date_to)]

        viewed = [p for p in progress_rows if p.status in ("in_progress", "completed")]
        completed = [p for p in progress_rows if p.status == "completed"]
        avg_progress = round(sum(p.progress_pct for p in progress_rows) / len(progress_rows)) if progress_rows else 0
        avg_view_time = round(sum(p.total_view_time_seconds for p in progress_rows) / len(progress_rows)) if progress_rows else 0

        rows.append({
            "content_id": str(c.id),
            "title": c.title,
            "type": c.type,
            "status": c.status,
            "eligible_count": len(eligible_ids),
            "viewed_count": len(viewed),
            "completed_count": len(completed),
            "avg_progress_pct": avg_progress,
            "avg_view_time_seconds": avg_view_time,
        })
    return rows


async def content_report_detail(
    db: AsyncSession,
    content: Content,
    *,
    dept_id: str | None = None,
    position_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    eligible_ids = set(await content_service.eligible_user_ids_for_content(db, content))
    users_q = select(User).where(User.id.in_(eligible_ids)) if eligible_ids else None
    if users_q is not None:
        if dept_id:
            users_q = users_q.where(User.dept_id == uuid.UUID(dept_id))
        if position_id:
            users_q = users_q.where(User.position_id == uuid.UUID(position_id))
        if user_id:
            users_q = users_q.where(User.id == uuid.UUID(user_id))
    users = list((await db.execute(users_q)).scalars().all()) if users_q is not None else []

    progress_result = await db.execute(
        select(UserContentProgress).where(
            UserContentProgress.content_id == content.id,
            UserContentProgress.user_id.in_([u.id for u in users]) if users else False,
        )
    ) if users else None
    progress_by_user = {p.user_id: p for p in progress_result.scalars().all()} if progress_result else {}

    dept_map, pos_map = await _dept_pos_label_maps(db, content.org_id)

    user_rows = []
    for u in users:
        p = progress_by_user.get(u.id)
        user_rows.append({
            "user_id": str(u.id),
            "full_name": u.full_name,
            "email": u.email,
            "department": dept_map.get(u.dept_id) if u.dept_id else None,
            "position": pos_map.get(u.position_id) if u.position_id else None,
            "status": p.status if p else "not_started",
            "progress_pct": p.progress_pct if p else 0,
            "view_time_seconds": p.total_view_time_seconds if p else 0,
            "started_at": p.started_at if p else None,
            "completed_at": p.completed_at if p else None,
            "last_viewed_at": p.last_viewed_at if p else None,
        })
    user_rows.sort(key=lambda r: (r["status"] != "completed", -r["progress_pct"]))
    return {"users": user_rows}


async def _dept_pos_label_maps(db: AsyncSession, org_id: uuid.UUID) -> tuple[dict, dict]:
    depts = list((await db.execute(select(Department).where(Department.org_id == org_id))).scalars().all())
    positions = list((await db.execute(select(Position).where(Position.org_id == org_id))).scalars().all())
    return {d.id: d.name for d in depts}, {p.id: p.name for p in positions}


# ─── گزارش سازمان‌ها ──────────────────────────────────────────────────────

async def organization_reports(db: AsyncSession, org_id: uuid.UUID | None) -> list[dict]:
    orgs_q = select(Organization)
    if org_id is not None:
        orgs_q = orgs_q.where(Organization.id == org_id)
    orgs = list((await db.execute(orgs_q)).scalars().all())

    rows = []
    for org in orgs:
        contents = await _published_contents(db, org.id)
        all_contents_q = select(Content).where(Content.org_id == org.id)
        contents_count = len(list((await db.execute(all_contents_q)).scalars().all()))

        users_q = select(User).where(User.org_id == org.id, User.role == "employee")
        users_count = len(list((await db.execute(users_q)).scalars().all()))

        progress_rows = await _progress_rows_for_contents(db, [c.id for c in contents])
        viewed = [p for p in progress_rows if p.status in ("in_progress", "completed")]
        completed = [p for p in progress_rows if p.status == "completed"]
        avg_progress = round(sum(p.progress_pct for p in progress_rows) / len(progress_rows)) if progress_rows else 0

        rows.append({
            "org_id": str(org.id),
            "org_name": org.name,
            "contents_count": contents_count,
            "users_count": users_count,
            "viewed_count": len(viewed),
            "completed_count": len(completed),
            "avg_progress_pct": avg_progress,
        })
    return rows


# ─── گزارش کاربران ────────────────────────────────────────────────────────

async def user_reports(
    db: AsyncSession, org_id: uuid.UUID | None, *, dept_id: str | None = None, position_id: str | None = None
) -> list[dict]:
    users_q = select(User).where(User.role == "employee")
    if org_id is not None:
        users_q = users_q.where(User.org_id == org_id)
    if dept_id:
        users_q = users_q.where(User.dept_id == uuid.UUID(dept_id))
    if position_id:
        users_q = users_q.where(User.position_id == uuid.UUID(position_id))
    users = list((await db.execute(users_q)).scalars().all())
    if not users:
        return []

    contents = await _published_contents(db, org_id)
    # Batch شده — یک کوئری برای همه‌ی محتواها به‌جای N کوئری در حلقه (رفع N+1)
    content_eligibility_map = await content_service.eligible_user_ids_map_for_contents(db, contents)
    eligible_map: dict[uuid.UUID, int] = {u.id: 0 for u in users}
    for uids in content_eligibility_map.values():
        for uid in uids:
            if uid in eligible_map:
                eligible_map[uid] += 1

    progress_rows = await _progress_rows_for_contents(db, [c.id for c in contents])
    by_user: dict[uuid.UUID, list[UserContentProgress]] = {}
    for p in progress_rows:
        by_user.setdefault(p.user_id, []).append(p)

    dept_map, pos_map = await _dept_pos_label_maps(db, org_id) if org_id else ({}, {})

    rows = []
    for u in users:
        u_progress = by_user.get(u.id, [])
        started = [p for p in u_progress if p.status in ("in_progress", "completed")]
        completed = [p for p in u_progress if p.status == "completed"]
        avg_progress = round(sum(p.progress_pct for p in u_progress) / len(u_progress)) if u_progress else 0
        last_activity = max((p.last_viewed_at for p in u_progress if p.last_viewed_at), default=None)
        rows.append({
            "user_id": str(u.id),
            "full_name": u.full_name,
            "email": u.email,
            "department": dept_map.get(u.dept_id) if u.dept_id else None,
            "position": pos_map.get(u.position_id) if u.position_id else None,
            "eligible_count": eligible_map.get(u.id, 0),
            "started_count": len(started),
            "completed_count": len(completed),
            "avg_progress_pct": avg_progress,
            "last_activity_at": last_activity,
        })
    rows.sort(key=lambda r: r["full_name"] or "")
    return rows
