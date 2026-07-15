"""
Talentick — Documents Router (Admin)
=======================================
مدیریت کتابخانه‌ی اسناد سازمانی (قوانین/آیین‌نامه‌ها/مستندات) — برای ادمین.

Routes:
  GET    /api/documents/categories       → لیست دسته‌بندی‌ها
  POST   /api/documents/categories       → ساخت دسته جدید
  PATCH  /api/documents/categories/{id}  → ویرایش دسته
  DELETE /api/documents/categories/{id}  → حذف دسته (اسناد آزاد می‌شوند — SET NULL)

  GET    /api/documents/                 → لیست کامل اسناد سازمان (بدون فیلتر دسترسی)
  POST   /api/documents/upload           → آپلود فایل سند به MinIO
  POST   /api/documents/                 → ثبت سند جدید (بعد از آپلود)
  GET    /api/documents/{id}             → جزئیات سند
  PATCH  /api/documents/{id}             → ویرایش سند
  DELETE /api/documents/{id}             → حذف سند

مشاهده‌ی کتابخانه برای کارمندان از routers/me.py (GET /api/me/documents) است —
آنجا Permission Engine (document_service.visibility_condition) اعمال می‌شود.

دسترسی: مدیریت (ساخت/ویرایش/حذف/آپلود) فقط manager به بالا — هم‌راستا با
سیاست فعلی پروژه برای ساختار سازمانی (routers/departments.py).
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_file
from app.database import get_db
from app.dependencies import Manager
from app.dependencies import enforce_org_scope as _enforce_org_scope
from app.schemas.content import UploadResponse
from app.schemas.document import (
    DocumentCategoryCreate,
    DocumentCategoryResponse,
    DocumentCategoryUpdate,
    DocumentCreate,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUpdate,
)
from app.services import document_service

router = APIRouter(prefix="/api/documents", tags=["Documents"])


# ─── Categories ──────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[DocumentCategoryResponse], summary="لیست دسته‌بندی‌های سند")
async def list_categories(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_categories(db, current_user.org_id)


@router.post(
    "/categories", response_model=DocumentCategoryResponse, status_code=status.HTTP_201_CREATED,
    summary="ساخت دسته‌بندی جدید",
)
async def create_category(
    body: DocumentCategoryCreate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    category = await document_service.create_category(db, current_user.org_id, body)
    return await document_service.category_to_response(db, category)


@router.patch("/categories/{category_id}", response_model=DocumentCategoryResponse, summary="ویرایش دسته‌بندی")
async def update_category(
    category_id: str,
    body: DocumentCategoryUpdate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    category = await document_service.get_category(db, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته یافت نشد")
    _enforce_org_scope(current_user, category.org_id)
    updated = await document_service.update_category(db, category, body)
    return await document_service.category_to_response(db, updated)


@router.delete(
    "/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT,
    summary="حذف دسته‌بندی",
    description="اسناد این دسته حذف نمی‌شوند — فقط category_id آن‌ها NULL می‌شود.",
)
async def delete_category(
    category_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    category = await document_service.get_category(db, category_id)
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته یافت نشد")
    _enforce_org_scope(current_user, category.org_id)
    await document_service.delete_category(db, category)


# ─── Upload ──────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, summary="آپلود فایل سند به MinIO")
async def upload_document_file(
    current_user: Manager,
    file: UploadFile = File(...),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    result = await upload_file(file, current_user.org_id, subfolder="documents")
    return UploadResponse(**result)


# ─── Documents ────────────────────────────────────────────────────────────────

@router.get("/", response_model=DocumentListResponse, summary="لیست کامل اسناد سازمان (مدیریتی)")
async def list_documents(
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    category_id: str | None = Query(None),
):
    items, total = await document_service.list_documents(
        db, current_user.org_id, page=page, page_size=page_size,
        search=search, category_id=category_id,
    )
    responses = [await document_service.document_to_response(db, d) for d in items]
    return DocumentListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/", response_model=DocumentDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ثبت سند جدید",
)
async def create_document(
    body: DocumentCreate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.create_document(db, current_user.org_id, current_user.id, body)
    return await document_service.document_to_detail(db, document)


@router.get("/{document_id}", response_model=DocumentDetailResponse, summary="جزئیات سند")
async def get_document(
    document_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند یافت نشد")
    _enforce_org_scope(current_user, document.org_id)
    return await document_service.document_to_detail(db, document)


@router.patch("/{document_id}", response_model=DocumentDetailResponse, summary="ویرایش سند")
async def update_document(
    document_id: str,
    body: DocumentUpdate,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند یافت نشد")
    _enforce_org_scope(current_user, document.org_id)
    updated = await document_service.update_document(db, document, body)
    return await document_service.document_to_detail(db, updated)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف سند")
async def delete_document(
    document_id: str,
    current_user: Manager,
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند یافت نشد")
    _enforce_org_scope(current_user, document.org_id)
    await document_service.delete_document(db, document)
