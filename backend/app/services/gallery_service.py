"""
Talentick — Gallery Service
==============================
CRUD گالری (مجموعه عکس) + جایگزینی لیست عکس‌ها. هر query با org_id
فیلتر می‌شود — هم‌ساختار با announcement_service (بدون targeting).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gallery import Gallery, GalleryPhoto
from app.models.organization import Organization
from app.models.user import User
from app.schemas.gallery import (
    GalleryCreate,
    GalleryDetailResponse,
    GalleryPhotoCreate,
    GalleryPhotoResponse,
    GalleryResponse,
    GalleryUpdate,
)


# ─── Photos ──────────────────────────────────────────────────────────────────

async def replace_photos(
    db: AsyncSession, gallery: Gallery, photos: list[GalleryPhotoCreate]
) -> None:
    await db.execute(GalleryPhoto.__table__.delete().where(GalleryPhoto.gallery_id == gallery.id))
    for p in photos:
        db.add(
            GalleryPhoto(
                id=uuid.uuid4(), gallery_id=gallery.id,
                image_url=p.image_url, order_index=p.order_index,
            )
        )
    await db.commit()


# ─── Mappers ────────────────────────────────────────────────────────────────

async def gallery_to_response(db: AsyncSession, gallery: Gallery) -> GalleryResponse:
    org = await db.get(Organization, gallery.org_id) if gallery.org_id else None
    creator_name = None
    if gallery.created_by:
        creator = await db.get(User, gallery.created_by)
        creator_name = creator.full_name if creator else None
    photo_count = (await db.execute(
        select(func.count()).select_from(GalleryPhoto).where(GalleryPhoto.gallery_id == gallery.id)
    )).scalar_one()
    return GalleryResponse(
        id=str(gallery.id),
        org_id=str(gallery.org_id) if gallery.org_id else None,
        org_name=org.name if org else None,
        title=gallery.title,
        description=gallery.description,
        cover_image_url=gallery.cover_image_url,
        is_active=gallery.is_active,
        created_by=str(gallery.created_by) if gallery.created_by else None,
        created_by_name=creator_name,
        photo_count=photo_count,
        created_at=gallery.created_at,
        updated_at=gallery.updated_at,
    )


async def gallery_to_detail(db: AsyncSession, gallery: Gallery) -> GalleryDetailResponse:
    base = await gallery_to_response(db, gallery)
    photos_result = await db.execute(
        select(GalleryPhoto).where(GalleryPhoto.gallery_id == gallery.id).order_by(GalleryPhoto.order_index)
    )
    photos = [
        GalleryPhotoResponse(id=str(p.id), image_url=p.image_url, order_index=p.order_index)
        for p in photos_result.scalars().all()
    ]
    return GalleryDetailResponse(**base.model_dump(), photos=photos)


# ─── Gallery CRUD ─────────────────────────────────────────────────────────

async def list_galleries(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    viewer: User | None = None,
    active_only: bool = False,
) -> tuple[list[Gallery], int]:
    q = select(Gallery)
    if viewer is not None:
        if org_id is not None:
            q = q.where(or_(Gallery.org_id == org_id, Gallery.org_id.is_(None)))
        else:
            q = q.where(Gallery.org_id.is_(None))
    elif org_id is not None:
        q = q.where(Gallery.org_id == org_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Gallery.title.ilike(like), Gallery.description.ilike(like)))
    if active_only:
        q = q.where(Gallery.is_active.is_(True))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Gallery.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_gallery(db: AsyncSession, gallery_id: str) -> Gallery | None:
    try:
        gid = uuid.UUID(gallery_id)
    except ValueError:
        return None
    return await db.get(Gallery, gid)


async def create_gallery(
    db: AsyncSession, org_id: uuid.UUID | None, created_by: uuid.UUID, data: GalleryCreate
) -> Gallery:
    gallery = Gallery(
        id=uuid.uuid4(),
        org_id=org_id,
        title=data.title,
        description=data.description,
        cover_image_url=data.cover_image_url,
        is_active=data.is_active,
        created_by=created_by,
    )
    db.add(gallery)
    await db.flush()
    if data.photos:
        await replace_photos(db, gallery, data.photos)
    await db.commit()
    await db.refresh(gallery)
    return gallery


async def update_gallery(db: AsyncSession, gallery: Gallery, data: GalleryUpdate) -> Gallery:
    payload = data.model_dump(exclude_unset=True, exclude={"photos"})
    for field, value in payload.items():
        setattr(gallery, field, value)
    await db.commit()
    await db.refresh(gallery)

    if data.photos is not None:
        await replace_photos(db, gallery, data.photos)
        await db.refresh(gallery)
    return gallery


async def delete_gallery(db: AsyncSession, gallery: Gallery) -> None:
    await db.delete(gallery)
    await db.commit()
