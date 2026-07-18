"""
Talentick — «محتواهای من» (My Contents) + «آزمون‌های من» (My Quizzes) Router
=================================================================================
پرتال کاربر عادی — کاملاً مستقل از API پنل ادمین (routers/content.py،
routers/quizzes.py).

Routes (محتوا):
  GET  /api/me/contents                                  → فهرست محتواهای مجاز من + پیشرفتم
  GET  /api/me/contents/{id}                              → جزئیات محتوا + آیتم‌ها + پیشرفت من
  POST /api/me/contents/{id}/start                        → شروع مشاهده (ثبت started_at)
  POST /api/me/contents/{id}/items/{item_id}/progress     → به‌روزرسانی پیشرفت یک آیتم

Routes (آزمون):
  GET  /api/me/quizzes/{id}                                → سوالات آزمون برای شرکت (بدون پاسخ صحیح)
  POST /api/me/quizzes/{id}/attempts                        → ثبت پاسخ‌ها + نمره‌دهی خودکار
  GET  /api/me/quizzes/{id}/attempts                        → تاریخچه‌ی تلاش‌های من روی این آزمون
  GET  /api/me/quizzes/{id}/attempts/{attempt_id}           → جزئیات یک تلاش (شامل پاسخ صحیح/توضیح)

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
from app.models.quiz import Quiz
from app.schemas.announcement import AnnouncementResponse
from app.schemas.content import CONTENT_TYPES
from app.schemas.department import DepartmentTreeNode
from app.schemas.document import DocumentCategoryResponse, DocumentListResponse
from app.schemas.me import (
    MyContentDetailResponse,
    MyContentItemResponse,
    MyContentListResponse,
    MyContentResponse,
)
from app.schemas.organization import OrganizationResponse
from app.schemas.progress import ItemProgressUpdate
from app.schemas.quiz import (
    QuizAttemptResult,
    QuizAttemptSubmit,
    QuizAttemptSummary,
    QuizTakeResponse,
)
from app.services import (
    announcement_service,
    content_service,
    department_service,
    document_service,
    org_service,
    progress_service,
    quiz_service,
)

router = APIRouter(prefix="/api/me", tags=["My Contents"])


async def _get_content_or_404(db: AsyncSession, content_id: str) -> Content:
    content = await content_service.get_content(db, content_id)
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "محتوا یافت نشد")
    return content


async def _get_active_quiz_or_404(db: AsyncSession, quiz_id: str, org_id) -> Quiz:
    quiz = await quiz_service.get_quiz(db, quiz_id)
    if not quiz or str(quiz.org_id) != str(org_id) or not quiz.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آزمون یافت نشد")
    return quiz


async def _enforce_quiz_item_lock(
    db: AsyncSession, current_user, quiz_id: str, content_id: str | None, item_id: str | None
) -> None:
    """
    اگر آزمون از طریق یک آیتم quiz_ref در یک محتوای «قفل ترتیبی» باز شده باشد
    (content_id/item_id در query string)، وضعیت قفل را enforce می‌کند —
    حتی اگر کاربر مستقیماً به URL آزمون برود و از UI محتوا رد نشود.
    """
    if not content_id or not item_id:
        return
    content = await content_service.get_content(db, content_id)
    if not content or str(content.org_id) != str(current_user.org_id):
        return
    item = await content_service.get_item(db, item_id)
    if not item or str(item.content_id) != str(content.id) or str(item.quiz_id) != str(quiz_id):
        return
    if await progress_service.is_item_locked(db, current_user.id, content, item):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این آزمون قفل است — ابتدا آیتم‌های قبلی را تکمیل کنید")


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
            **base.model_dump(exclude={"org_id", "org_name", "status", "created_by", "created_by_name", "updated_at", "sequential_progress", "target_count"}),
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
    locked_map = progress_service.compute_locked_map(content, detail.items, item_progress_map)

    items = [
        MyContentItemResponse(
            **it.model_dump(exclude={"content_id", "created_at"}),
            my_status=(item_progress_map.get(it.id).status if it.id in item_progress_map else "not_started"),
            my_progress_pct=(item_progress_map.get(it.id).progress_pct if it.id in item_progress_map else 0),
            my_last_position=(item_progress_map.get(it.id).last_position if it.id in item_progress_map else None),
            is_locked=locked_map.get(it.id, False),
        )
        for it in detail.items
    ]
    return MyContentDetailResponse(
        **detail.model_dump(exclude={"org_id", "org_name", "status", "created_by", "created_by_name", "updated_at", "sequential_progress", "target_count", "items", "targets"}),
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
    if await progress_service.is_item_locked(db, current_user.id, content, item):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این آیتم قفل است — ابتدا آیتم‌های قبلی را تکمیل کنید")

    item_progress, content_progress = await progress_service.update_item_progress(
        db, current_user, content, item, body
    )
    return {
        "item": progress_service.item_progress_to_response(item_progress),
        "content": progress_service.content_progress_to_response(content_progress),
    }


# ─── Org Intro + Org Chart + Document Library ────────────────────────────────
# صفحه‌ی «سازمان» کارمند: معرفی سازمان، چارت سازمانی (فقط مشاهده)، کتابخانه اسناد.

@router.get("/org", response_model=OrganizationResponse, summary="معرفی سازمان (تاریخچه/ماموریت/چشم‌انداز/ارزش‌ها)")
async def get_my_org(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    org = await org_service.get_organization(db, current_user.org_id)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سازمان یافت نشد")
    return org


@router.get("/org-chart", response_model=list[DepartmentTreeNode], summary="چارت سازمانی (فقط مشاهده)")
async def get_my_org_chart(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    return await department_service.build_tree(db, current_user.org_id)


@router.get("/documents/categories", response_model=list[DocumentCategoryResponse], summary="دسته‌بندی‌های کتابخانه اسناد")
async def list_my_document_categories(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    return await document_service.list_categories(db, current_user.org_id)


@router.get("/documents", response_model=DocumentListResponse, summary="کتابخانه اسناد — قوانین/آیین‌نامه‌ها/مستندات مجاز من")
async def list_my_documents(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    category_id: str | None = Query(None),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    items, total = await document_service.list_documents(
        db, current_user.org_id, page=page, page_size=page_size,
        search=search, category_id=category_id,
        viewer=current_user, apply_visibility=True,
    )
    responses = [await document_service.document_to_response(db, d) for d in items]
    return DocumentListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get(
    "/announcements", response_model=list[AnnouncementResponse],
    summary="اطلاعیه‌های فعال و مجاز من (صفحه‌ی خانه)",
    description="اطلاعیه‌های تک‌فایلی (عکس/ویدیو) که هم در بازه‌ی نمایش‌شان هستند (starts_at/ends_at) و هم طبق دسترسی واحد/نقش برای این کاربر مجازند — جدیدترین اول.",
)
async def list_my_announcements(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    items, _ = await announcement_service.list_announcements(
        db, current_user.org_id, page=1, page_size=limit,
        viewer=current_user, apply_visibility=True, active_only=True,
    )
    return [await announcement_service.announcement_to_response(db, a) for a in items]


# ─── Quiz Routes ─────────────────────────────────────────────────────────────

@router.get(
    "/quizzes/{quiz_id}", response_model=QuizTakeResponse,
    summary="سوالات آزمون برای شرکت (بدون پاسخ صحیح)",
    description="پاسخ صحیح و توضیح سوالات عمداً در این پاسخ نیست — فقط بعد از ثبت attempt نمایش داده می‌شود.",
)
async def get_quiz_to_take(
    quiz_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    content_id: str | None = Query(None, description="در صورت باز شدن از یک آیتم quiz_ref — برای enforcement قفل ترتیبی"),
    item_id: str | None = Query(None, description="در صورت باز شدن از یک آیتم quiz_ref — برای enforcement قفل ترتیبی"),
) -> QuizTakeResponse:
    quiz = await _get_active_quiz_or_404(db, quiz_id, current_user.org_id)
    await _enforce_quiz_item_lock(db, current_user, quiz_id, content_id, item_id)
    return await quiz_service.get_quiz_for_taking(db, quiz, current_user)


@router.post(
    "/quizzes/{quiz_id}/attempts", response_model=QuizAttemptResult, status_code=status.HTTP_201_CREATED,
    summary="ثبت پاسخ‌های آزمون (نمره‌دهی خودکار)",
    description="""
    یک‌بار ثبت می‌شود — attempt هرگز ویرایش نمی‌شود. پاسخ صحیح/توضیح هر
    سوال فقط در همین پاسخ (بعد از ثبت) نمایش داده می‌شود.

    **خطاها:**
    - `400` — تعداد دفعات مجاز (`max_attempts`) پر شده یا مهلت زمانی (`time_limit_min`) گذشته است.
    """,
    responses={400: {"description": "تعداد دفعات مجاز پر شده یا مهلت زمانی گذشته است"}},
)
async def submit_quiz_attempt(
    quiz_id: str,
    body: QuizAttemptSubmit,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    content_id: str | None = Query(None, description="در صورت باز شدن از یک آیتم quiz_ref — برای enforcement قفل ترتیبی"),
    item_id: str | None = Query(None, description="در صورت باز شدن از یک آیتم quiz_ref — برای enforcement قفل ترتیبی"),
) -> QuizAttemptResult:
    quiz = await _get_active_quiz_or_404(db, quiz_id, current_user.org_id)
    await _enforce_quiz_item_lock(db, current_user, quiz_id, content_id, item_id)
    attempt = await quiz_service.submit_attempt(db, current_user, quiz, body)
    return await quiz_service.attempt_to_result(db, attempt)


@router.get(
    "/quizzes/{quiz_id}/attempts", response_model=list[QuizAttemptSummary],
    summary="تاریخچه‌ی تلاش‌های من روی این آزمون",
)
async def list_my_quiz_attempts(
    quiz_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
) -> list[QuizAttemptSummary]:
    quiz = await _get_active_quiz_or_404(db, quiz_id, current_user.org_id)
    attempts = await quiz_service.list_my_attempts(db, current_user.id, quiz.id)
    return [quiz_service.attempt_to_summary(a) for a in attempts]


@router.get(
    "/quizzes/{quiz_id}/attempts/{attempt_id}", response_model=QuizAttemptResult,
    summary="جزئیات یک تلاش (شامل پاسخ صحیح/توضیح)",
)
async def get_my_quiz_attempt(
    quiz_id: str,
    attempt_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
) -> QuizAttemptResult:
    quiz = await _get_active_quiz_or_404(db, quiz_id, current_user.org_id)
    attempt = await quiz_service.get_attempt(db, attempt_id)
    if (
        not attempt
        or str(attempt.quiz_id) != str(quiz.id)
        or str(attempt.user_id) != str(current_user.id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تلاش یافت نشد")
    return await quiz_service.attempt_to_result(db, attempt)
