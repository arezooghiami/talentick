"""
Talentick — Document Service
================================
CRUD کتابخانه‌ی اسناد (Document/DocumentCategory) + Permission Engine ساده
مبتنی بر واحد/نقش (OR) — هر query با org_id فیلتر می‌شود.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DOCUMENT_TARGET_TYPES, Document, DocumentCategory, DocumentTarget
from app.models.organization import Department
from app.models.user import VALID_ROLES, User
from app.schemas.document import (
    DocumentCategoryCreate,
    DocumentCategoryResponse,
    DocumentCategoryUpdate,
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentTargetCreate,
    DocumentTargetResponse,
    DocumentUpdate,
)


# ─── DocumentCategory ────────────────────────────────────────────────────────

async def list_categories(db: AsyncSession, org_id: uuid.UUID) -> list[DocumentCategoryResponse]:
    result = await db.execute(
        select(DocumentCategory)
        .where(DocumentCategory.org_id == org_id)
        .order_by(DocumentCategory.order_index, DocumentCategory.created_at)
    )
    categories = list(result.scalars().all())
    counts_result = await db.execute(
        select(Document.category_id, func.count())
        .where(Document.org_id == org_id, Document.category_id.is_not(None))
        .group_by(Document.category_id)
    )
    counts = {str(cid): c for cid, c in counts_result.all()}
    return [
        DocumentCategoryResponse(
            id=str(c.id), name=c.name, order_index=c.order_index,
            document_count=counts.get(str(c.id), 0), created_at=c.created_at,
        )
        for c in categories
    ]


async def category_to_response(db: AsyncSession, category: DocumentCategory) -> DocumentCategoryResponse:
    count = (await db.execute(
        select(func.count()).select_from(Document).where(Document.category_id == category.id)
    )).scalar_one()
    return DocumentCategoryResponse(
        id=str(category.id), name=category.name, order_index=category.order_index,
        document_count=count, created_at=category.created_at,
    )


async def get_category(db: AsyncSession, category_id: str) -> DocumentCategory | None:
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        return None
    return await db.get(DocumentCategory, cid)


async def create_category(
    db: AsyncSession, org_id: uuid.UUID, data: DocumentCategoryCreate
) -> DocumentCategory:
    category = DocumentCategory(
        id=uuid.uuid4(), org_id=org_id, name=data.name, order_index=data.order_index,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession, category: DocumentCategory, data: DocumentCategoryUpdate
) -> DocumentCategory:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, category: DocumentCategory) -> None:
    await db.delete(category)
    await db.commit()


# ─── Targeting (دسترسی: واحد/نقش) ───────────────────────────────────────────

async def _validate_targets(
    db: AsyncSession, org_id: uuid.UUID, targets: list[DocumentTargetCreate]
) -> None:
    for t in targets:
        if t.target_type not in DOCUMENT_TARGET_TYPES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"نوع هدف نامعتبر است — مقادیر مجاز: {', '.join(DOCUMENT_TARGET_TYPES)}",
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


async def _target_to_response(db: AsyncSession, target: DocumentTarget) -> DocumentTargetResponse:
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
    return DocumentTargetResponse(
        id=str(target.id), target_type=target.target_type,
        target_id=target.target_value, target_label=label,
    )


async def _create_targets(
    db: AsyncSession, org_id: uuid.UUID, document_id: uuid.UUID, targets: list[DocumentTargetCreate]
) -> None:
    seen: set[tuple[str, str]] = set()
    for t in targets:
        key = (t.target_type, t.target_id)
        if key in seen:
            continue
        seen.add(key)
        db.add(
            DocumentTarget(
                id=uuid.uuid4(), org_id=org_id, document_id=document_id,
                target_type=t.target_type, target_value=t.target_id,
            )
        )


async def replace_targets(
    db: AsyncSession, document: Document, targets: list[DocumentTargetCreate]
) -> None:
    await _validate_targets(db, document.org_id, targets)
    await db.execute(
        DocumentTarget.__table__.delete().where(DocumentTarget.document_id == document.id)
    )
    await _create_targets(db, document.org_id, document.id, targets)
    await db.commit()


def visibility_condition(viewer: User):
    """
    شرط SQL — بدون هیچ target برای سند = قابل مشاهده برای کل سازمان.
    با وجود target: کافیست کاربر با یکی از سطرها مطابقت داشته باشد (OR بین
    department/role) — دسترسی سند به‌مراتب ساده‌تر از Permission Engine
    محتوا است، چون نیازی به AND بین ابعاد نیست.
    """
    has_targets = exists(
        select(DocumentTarget.id).where(DocumentTarget.document_id == Document.id)
    )
    role_match = exists(
        select(DocumentTarget.id).where(
            DocumentTarget.document_id == Document.id,
            DocumentTarget.target_type == "role",
            DocumentTarget.target_value == viewer.role,
        )
    )
    if viewer.dept_id:
        dept_match = exists(
            select(DocumentTarget.id).where(
                DocumentTarget.document_id == Document.id,
                DocumentTarget.target_type == "department",
                DocumentTarget.target_value == str(viewer.dept_id),
            )
        )
        return or_(~has_targets, dept_match, role_match)
    return or_(~has_targets, role_match)


async def is_visible_to_user(db: AsyncSession, document: Document, viewer: User) -> bool:
    q = select(Document.id).where(Document.id == document.id, visibility_condition(viewer))
    result = await db.execute(q)
    return result.scalar_one_or_none() is not None


# ─── Mappers ────────────────────────────────────────────────────────────────

async def document_to_response(db: AsyncSession, document: Document) -> DocumentResponse:
    category_name = None
    if document.category_id:
        category = await db.get(DocumentCategory, document.category_id)
        category_name = category.name if category else None
    uploader_name = None
    if document.uploaded_by:
        uploader = await db.get(User, document.uploaded_by)
        uploader_name = uploader.full_name if uploader else None
    target_count = (await db.execute(
        select(func.count()).select_from(DocumentTarget).where(DocumentTarget.document_id == document.id)
    )).scalar_one()
    return DocumentResponse(
        id=str(document.id),
        org_id=str(document.org_id),
        title=document.title,
        description=document.description,
        category_id=str(document.category_id) if document.category_id else None,
        category_name=category_name,
        file_url=document.file_url,
        file_name=document.file_name,
        file_size=document.file_size,
        file_type=document.file_type,
        uploaded_by=str(document.uploaded_by) if document.uploaded_by else None,
        uploaded_by_name=uploader_name,
        target_count=target_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def document_to_detail(db: AsyncSession, document: Document) -> DocumentDetailResponse:
    base = await document_to_response(db, document)
    targets_result = await db.execute(
        select(DocumentTarget).where(DocumentTarget.document_id == document.id)
    )
    targets = [await _target_to_response(db, t) for t in targets_result.scalars().all()]
    return DocumentDetailResponse(**base.model_dump(), targets=targets)


# ─── Document CRUD ────────────────────────────────────────────────────────

async def list_documents(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    category_id: str | None = None,
    viewer: User | None = None,
    apply_visibility: bool = False,
) -> tuple[list[Document], int]:
    q = select(Document).where(Document.org_id == org_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Document.title.ilike(like), Document.description.ilike(like)))
    if category_id:
        try:
            q = q.where(Document.category_id == uuid.UUID(category_id))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه دسته نامعتبر است")
    if apply_visibility and viewer is not None:
        q = q.where(visibility_condition(viewer))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_document(db: AsyncSession, document_id: str) -> Document | None:
    try:
        did = uuid.UUID(document_id)
    except ValueError:
        return None
    return await db.get(Document, did)


async def create_document(
    db: AsyncSession, org_id: uuid.UUID, uploaded_by: uuid.UUID, data: DocumentCreate
) -> Document:
    if data.targets:
        await _validate_targets(db, org_id, data.targets)
    if data.category_id:
        category = await get_category(db, data.category_id)
        if not category or str(category.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته انتخاب‌شده معتبر نیست")

    document = Document(
        id=uuid.uuid4(),
        org_id=org_id,
        category_id=uuid.UUID(data.category_id) if data.category_id else None,
        title=data.title,
        description=data.description,
        file_url=data.file_url,
        file_name=data.file_name,
        file_size=data.file_size,
        file_type=data.file_type,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    await db.flush()
    if data.targets:
        await _create_targets(db, org_id, document.id, data.targets)
    await db.commit()
    await db.refresh(document)
    return document


async def update_document(db: AsyncSession, document: Document, data: DocumentUpdate) -> Document:
    payload = data.model_dump(exclude_unset=True, exclude={"targets"})
    if "category_id" in payload:
        cid = payload["category_id"]
        if cid:
            category = await get_category(db, cid)
            if not category or str(category.org_id) != str(document.org_id):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته انتخاب‌شده معتبر نیست")
            payload["category_id"] = uuid.UUID(cid)
        else:
            payload["category_id"] = None
    for field, value in payload.items():
        setattr(document, field, value)
    await db.commit()
    await db.refresh(document)

    if data.targets is not None:
        await replace_targets(db, document, data.targets)
        await db.refresh(document)
    return document


async def delete_document(db: AsyncSession, document: Document) -> None:
    await db.delete(document)
    await db.commit()
