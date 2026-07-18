"""
Talentick — Announcement Service
====================================
CRUD اطلاعیه‌ی تک‌فایلی (Announcement) + Permission Engine ساده مبتنی بر
واحد/نقش (OR) — هم‌ساختار با document_service. هر query با org_id
فیلتر می‌شود.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import (
    ANNOUNCEMENT_TARGET_TYPES,
    Announcement,
    AnnouncementTarget,
)
from app.models.organization import Department, Organization
from app.models.user import VALID_ROLES, User
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementDetailResponse,
    AnnouncementResponse,
    AnnouncementTargetCreate,
    AnnouncementTargetResponse,
    AnnouncementUpdate,
)


# ─── Targeting (دسترسی: واحد/نقش) ───────────────────────────────────────────

async def _validate_targets(
    db: AsyncSession, org_id: uuid.UUID, targets: list[AnnouncementTargetCreate]
) -> None:
    for t in targets:
        if t.target_type not in ANNOUNCEMENT_TARGET_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"نوع هدف نامعتبر است — مقادیر مجاز: {', '.join(ANNOUNCEMENT_TARGET_TYPES)}",
            )
        if t.target_type == "department":
            try:
                dept_uuid = uuid.UUID(t.target_id)
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه واحد نامعتبر است")
            dept = await db.get(Department, dept_uuid)
            if not dept or str(dept.org_id) != str(org_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد انتخاب‌شده معتبر نیست")
        elif t.target_type == "role":
            if t.target_id not in VALID_ROLES:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "نقش انتخاب‌شده معتبر نیست")


async def _target_to_response(db: AsyncSession, target: AnnouncementTarget) -> AnnouncementTargetResponse:
    label = None
    if target.target_type == "department":
        try:
            dept = await db.get(Department, uuid.UUID(target.target_value))
            label = dept.name if dept else None
        except ValueError:
            label = None
    elif target.target_type == "role":
        label = {
            "super_admin": "سوپر ادمین", "org_admin": "ادمین سازمان",
            "manager": "مدیر", "employee": "کارمند",
        }.get(target.target_value, target.target_value)
    return AnnouncementTargetResponse(
        id=str(target.id), target_type=target.target_type,
        target_id=target.target_value, target_label=label,
    )


async def _create_targets(
    db: AsyncSession, org_id: uuid.UUID, announcement_id: uuid.UUID, targets: list[AnnouncementTargetCreate]
) -> None:
    seen: set[tuple[str, str]] = set()
    for t in targets:
        key = (t.target_type, t.target_id)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            AnnouncementTarget(
                id=uuid.uuid4(), org_id=org_id, announcement_id=announcement_id,
                target_type=t.target_type, target_value=t.target_id,
            )
        )


async def replace_targets(
    db: AsyncSession, announcement: Announcement, targets: list[AnnouncementTargetCreate]
) -> None:
    await _validate_targets(db, announcement.org_id, targets)
    await db.execute(
        AnnouncementTarget.__table__.delete().where(AnnouncementTarget.announcement_id == announcement.id)
    )
    await _create_targets(db, announcement.org_id, announcement.id, targets)
    await db.commit()


def visibility_condition(viewer: User):
    """بدون target = کل سازمان؛ با وجود target کافیست department یا role مطابقت داشته باشد (OR)."""
    has_targets = exists(
        select(AnnouncementTarget.id).where(AnnouncementTarget.announcement_id == Announcement.id)
    )
    role_match = exists(
        select(AnnouncementTarget.id).where(
            AnnouncementTarget.announcement_id == Announcement.id,
            AnnouncementTarget.target_type == "role",
            AnnouncementTarget.target_value == viewer.role,
        )
    )
    if viewer.dept_id:
        dept_match = exists(
            select(AnnouncementTarget.id).where(
                AnnouncementTarget.announcement_id == Announcement.id,
                AnnouncementTarget.target_type == "department",
                AnnouncementTarget.target_value == str(viewer.dept_id),
            )
        )
        return or_(~has_targets, dept_match, role_match)
    return or_(~has_targets, role_match)


def is_currently_active(announcement: Announcement) -> bool:
    """آیا اطلاعیه الان در بازه‌ی نمایش است؟ (is_active + starts_at/ends_at)."""
    if not announcement.is_active:
        return False
    now = datetime.now(timezone.utc)
    if announcement.starts_at and announcement.starts_at > now:
        return False
    if announcement.ends_at and announcement.ends_at < now:
        return False
    return True


def _active_window_clause():
    now = datetime.now(timezone.utc)
    return (
        Announcement.is_active.is_(True),
        or_(Announcement.starts_at.is_(None), Announcement.starts_at <= now),
        or_(Announcement.ends_at.is_(None), Announcement.ends_at >= now),
    )


# ─── Mappers ────────────────────────────────────────────────────────────────

async def announcement_to_response(db: AsyncSession, announcement: Announcement) -> AnnouncementResponse:
    org = await db.get(Organization, announcement.org_id)
    creator_name = None
    if announcement.created_by:
        creator = await db.get(User, announcement.created_by)
        creator_name = creator.full_name if creator else None
    target_count = (await db.execute(
        select(func.count()).select_from(AnnouncementTarget).where(
            AnnouncementTarget.announcement_id == announcement.id
        )
    )).scalar_one()
    return AnnouncementResponse(
        id=str(announcement.id),
        org_id=str(announcement.org_id),
        org_name=org.name if org else None,
        title=announcement.title,
        description=announcement.description,
        media_url=announcement.media_url,
        media_type=announcement.media_type,
        file_name=announcement.file_name,
        file_size=announcement.file_size,
        starts_at=announcement.starts_at,
        ends_at=announcement.ends_at,
        is_active=announcement.is_active,
        created_by=str(announcement.created_by) if announcement.created_by else None,
        created_by_name=creator_name,
        target_count=target_count,
        created_at=announcement.created_at,
        updated_at=announcement.updated_at,
    )


async def announcement_to_detail(db: AsyncSession, announcement: Announcement) -> AnnouncementDetailResponse:
    base = await announcement_to_response(db, announcement)
    targets_result = await db.execute(
        select(AnnouncementTarget).where(AnnouncementTarget.announcement_id == announcement.id)
    )
    targets = [await _target_to_response(db, t) for t in targets_result.scalars().all()]
    return AnnouncementDetailResponse(**base.model_dump(), targets=targets)


# ─── Announcement CRUD ────────────────────────────────────────────────────

async def list_announcements(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    viewer: User | None = None,
    apply_visibility: bool = False,
    active_only: bool = False,
) -> tuple[list[Announcement], int]:
    q = select(Announcement)
    if org_id is not None:
        q = q.where(Announcement.org_id == org_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Announcement.title.ilike(like), Announcement.description.ilike(like)))
    if active_only:
        q = q.where(*_active_window_clause())
    if apply_visibility and viewer is not None:
        q = q.where(visibility_condition(viewer))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Announcement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_announcement(db: AsyncSession, announcement_id: str) -> Announcement | None:
    try:
        aid = uuid.UUID(announcement_id)
    except ValueError:
        return None
    return await db.get(Announcement, aid)


async def create_announcement(
    db: AsyncSession, org_id: uuid.UUID, created_by: uuid.UUID, data: AnnouncementCreate
) -> Announcement:
    if data.media_type not in ("image", "video"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع فایل باید image یا video باشد")
    if data.targets:
        await _validate_targets(db, org_id, data.targets)

    announcement = Announcement(
        id=uuid.uuid4(),
        org_id=org_id,
        title=data.title,
        description=data.description,
        media_url=data.media_url,
        media_type=data.media_type,
        file_name=data.file_name,
        file_size=data.file_size,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        is_active=data.is_active,
        created_by=created_by,
    )
    db.add(announcement)
    await db.flush()
    if data.targets:
        await _create_targets(db, org_id, announcement.id, data.targets)
    await db.commit()
    await db.refresh(announcement)
    return announcement


async def update_announcement(
    db: AsyncSession, announcement: Announcement, data: AnnouncementUpdate
) -> Announcement:
    payload = data.model_dump(exclude_unset=True, exclude={"targets"})
    if "media_type" in payload and payload["media_type"] not in ("image", "video"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع فایل باید image یا video باشد")
    for field, value in payload.items():
        setattr(announcement, field, value)
    await db.commit()
    await db.refresh(announcement)

    if data.targets is not None:
        await replace_targets(db, announcement, data.targets)
        await db.refresh(announcement)
    return announcement


async def delete_announcement(db: AsyncSession, announcement: Announcement) -> None:
    await db.delete(announcement)
    await db.commit()
