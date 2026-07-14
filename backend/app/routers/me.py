"""
Talentick — «محتواهای من» (My Contents) Router
==================================================
پرتال کاربر عادی — کاملاً مستقل از API پنل ادمین (routers/content.py).

Routes:
  GET  /api/me/contents                                  → فهرست محتواهای مجاز من + پیشرفتم
  GET  /api/me/contents/{id}                              → جزئیات محتوا + آیتم‌ها + پیشرفت من
  POST /api/me/contents/{id}/start                        → شروع مشاهده (ثبت started_at)
  POST /api/me/contents/{id}/items/{item_id}/progress     → به‌روزرسانی پیشرفت یک آیتم

دسترسی: هر کاربر فعال (Employee و بالاتر) — همیشه از Permission Engine مرکزی
(content_service.visibility_condition) استفاده می‌شود، صرف‌نظر از نقش کاربر،
چون این صفحه شخصی («محتواهای من») است نه پنل مدیریت.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import Employee
from app.models.content import Content
from app.schemas.content import CONTENT_TYPES
from app.schemas.me import (
    MyContentDetailResponse,
    MyContentItemResponse,
    MyContentListResponse,
    MyContentResponse,
)
from app.schemas.progress import ItemProgressUpdate
from app.services import content_service, progress_service

router = APIRouter(prefix="/api/me", tags=["My Contents"])


async def _get_content_or_404(db: AsyncSession, content_id: str) -> Content:
    content = await content_service.get_content(db, content_id)
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    return content


@router.get("/contents", response_model=MyContentListResponse, summary="فهرست محتواهای مجاز من")
async def list_my_contents(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    type: str | None = Query(None, description="course | article | podcast | book"),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    if type and type not in CONTENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نوع محتوا نامعتبر — مقادیر مجاز: {', '.join(CONTENT_TYPES)}")

    items, total = await content_service.list_contents(
        db, current_user.org_id, page=page, page_size=page_size,
        search=search, type_filter=type, status_filter="published",
        viewer=current_user, apply_visibility=True,
    )
    progress_map = await progress_service.get_content_progress_map(
        db, current_user.id, [c.id for c in items]
    )
    responses = []
    for c in items:
        base = await content_service.content_to_response(db, c)
        p = progress_map.get(str(c.id))
        responses.append(MyContentResponse(
            **base.model_dump(exclude={"org_id", "status", "created_by", "created_by_name", "updated_at"}),
            my_status=p.status if p else "not_started",
            my_progress_pct=p.progress_pct if p else 0,
            my_last_item_id=str(p.last_item_id) if p and p.last_item_id else None,
            my_last_viewed_at=p.last_viewed_at if p else None,
        ))
    return MyContentListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/contents/{content_id}", response_model=MyContentDetailResponse, summary="جزئیات محتوا + پیشرفت من")
async def get_my_content(
    content_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    if str(content.org_id) != str(current_user.org_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    if content.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    if not await content_service.is_visible_to_user(db, content, current_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")

    detail = await content_service.content_to_detail(db, content)
    content_progress = await progress_service.get_content_progress(db, current_user.id, content.id)
    item_progress_map = await progress_service.get_item_progress_map(db, current_user.id, content.id)

    items = [
        MyContentItemResponse(
            **it.model_dump(exclude={"content_id", "created_at"}),
            my_status=(item_progress_map.get(it.id).status if it.id in item_progress_map else "not_started"),
            my_progress_pct=(item_progress_map.get(it.id).progress_pct if it.id in item_progress_map else 0),
            my_last_position=(item_progress_map.get(it.id).last_position if it.id in item_progress_map else None),
        )
        for it in detail.items
    ]
    return MyContentDetailResponse(
        **detail.model_dump(exclude={"org_id", "status", "created_by", "created_by_name", "updated_at", "items", "targets"}),
        items=items,
        my_status=content_progress.status if content_progress else "not_started",
        my_progress_pct=content_progress.progress_pct if content_progress else 0,
        my_last_item_id=str(content_progress.last_item_id) if content_progress and content_progress.last_item_id else None,
        my_last_viewed_at=content_progress.last_viewed_at if content_progress else None,
    )


@router.post("/contents/{content_id}/start", summary="شروع مشاهده محتوا")
async def start_my_content(
    content_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    if str(content.org_id) != str(current_user.org_id) or content.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    if not await content_service.is_visible_to_user(db, content, current_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    progress = await progress_service.start_content(db, current_user, content)
    return progress_service.content_progress_to_response(progress)


@router.post(
    "/contents/{content_id}/items/{item_id}/progress",
    summary="به‌روزرسانی پیشرفت یک آیتم (Progress Tracking)",
)
async def update_item_progress(
    content_id: str,
    item_id: str,
    body: ItemProgressUpdate,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    content = await _get_content_or_404(db, content_id)
    if str(content.org_id) != str(current_user.org_id) or content.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    if not await content_service.is_visible_to_user(db, content, current_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")

    item = await content_service.get_item(db, item_id)
    if not item or str(item.content_id) != str(content.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آیتم یافت نشد")

    item_progress, content_progress = await progress_service.update_item_progress(
        db, current_user, content, item, body
    )
    return {
        "item": progress_service.item_progress_to_response(item_progress),
        "content": progress_service.content_progress_to_response(content_progress),
    }
