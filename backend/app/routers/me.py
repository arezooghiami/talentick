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
from app.schemas.onboarding import (
    MyEnrollmentDetailResponse,
    MyEnrollmentResponse,
    StepCompleteRequest,
)
from app.schemas.organization import OrganizationResponse
from app.schemas.points import PointsHistoryResponse, PointsSummaryResponse, WalletResponse
from app.schemas.progress import ItemProgressUpdate
from app.schemas.reward import (
    RedemptionCreate,
    RedemptionListResponse,
    RedemptionResponse,
    RewardListResponse,
)
from app.schemas.quiz import (
    QuizAttemptResult,
    QuizAttemptSubmit,
    QuizAttemptSummary,
    QuizTakeResponse,
)
from app.schemas.ticket import (
    TicketCloseRequest,
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketMessageCreate,
    TicketMessageResponse,
)
from app.services import (
    announcement_service,
    content_service,
    department_service,
    document_service,
    onboarding_service,
    org_service,
    points_service,
    progress_service,
    quiz_service,
    redemption_service,
    reward_service,
    ticket_service,
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


# ─── Onboarding Routes («مسیر آنبوردینگ من») ──────────────────────────────

@router.get(
    "/onboarding", response_model=list[MyEnrollmentResponse],
    summary="برنامه‌های آشنایی که در آن‌ها ثبت‌نام شده‌ام",
    description="برنامه‌های در حال انجام قبل از تکمیل‌شده‌ها، و هرکدام بر اساس جدیدترین تاریخ ثبت‌نام مرتب می‌شوند.",
)
async def list_my_onboarding(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    return await onboarding_service.get_my_enrollments(db, current_user)


@router.get(
    "/onboarding/{enrollment_id}", response_model=MyEnrollmentDetailResponse,
    summary="جزئیات یک برنامه‌ی آشنایی + وضعیت من در هر مرحله",
)
async def get_my_onboarding_detail(
    enrollment_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    enrollment = await onboarding_service.get_enrollment_for_user(db, current_user, enrollment_id)
    if not enrollment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ثبت‌نام یافت نشد")
    return await onboarding_service.get_my_enrollment_detail(db, enrollment)


@router.post(
    "/onboarding/steps/{step_id}/complete", response_model=MyEnrollmentDetailResponse,
    summary="علامت‌گذاری یک مرحله به‌عنوان انجام‌شده",
)
async def complete_onboarding_step(
    step_id: str,
    body: StepCompleteRequest,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    step_progress = await onboarding_service.get_step_progress_for_user(db, current_user, step_id)
    if not step_progress:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرحله یافت نشد")
    await onboarding_service.set_step_status(db, step_progress, "completed", body.notes)
    enrollment = await onboarding_service.get_enrollment_for_user(db, current_user, str(step_progress.enrollment_id))
    return await onboarding_service.get_my_enrollment_detail(db, enrollment)


@router.post(
    "/onboarding/steps/{step_id}/skip", response_model=MyEnrollmentDetailResponse,
    summary="رد کردن یک مرحله‌ی اختیاری",
    description="فقط برای مراحلی که is_required=False است — رد کردن مرحله‌ی اجباری خطای 400 می‌دهد.",
)
async def skip_onboarding_step(
    step_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    step_progress = await onboarding_service.get_step_progress_for_user(db, current_user, step_id)
    if not step_progress:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرحله یافت نشد")
    await onboarding_service.set_step_status(db, step_progress, "skipped")
    enrollment = await onboarding_service.get_enrollment_for_user(db, current_user, str(step_progress.enrollment_id))
    return await onboarding_service.get_my_enrollment_detail(db, enrollment)


# ─── Ticket Routes («تیکت‌های من») ─────────────────────────────────────────

async def _get_my_ticket_or_404(db: AsyncSession, current_user, ticket_id: str):
    ticket = await ticket_service.get_ticket(db, ticket_id)
    if not ticket or str(ticket.created_by) != str(current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تیکت یافت نشد")
    return ticket


@router.post(
    "/tickets", response_model=TicketDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ثبت تیکت جدید (درخواست/بازخورد/سؤال)",
)
async def create_my_ticket(
    body: TicketCreate,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    ticket = await ticket_service.create_ticket(db, current_user.org_id, current_user, body)
    return await ticket_service.ticket_to_detail(db, ticket)


@router.get("/tickets", response_model=TicketListResponse, summary="لیست تیکت‌های من")
async def list_my_tickets(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
):
    items, total = await ticket_service.list_tickets(
        db, None, created_by=current_user.id, status_filter=status_filter,
        page=page, page_size=page_size,
    )
    responses = [await ticket_service.ticket_to_response(db, t) for t in items]
    return TicketListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetailResponse, summary="جزئیات یک تیکت من + ترد پیام‌ها")
async def get_my_ticket(
    ticket_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_my_ticket_or_404(db, current_user, ticket_id)
    return await ticket_service.ticket_to_detail(db, ticket)


@router.post(
    "/tickets/{ticket_id}/messages", response_model=TicketMessageResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن پیام به تیکت خودم",
)
async def reply_to_my_ticket(
    ticket_id: str,
    body: TicketMessageCreate,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_my_ticket_or_404(db, current_user, ticket_id)
    message = await ticket_service.add_message(db, ticket, current_user, body.body, is_staff_reply=False)
    return await ticket_service.message_to_response(db, message)


@router.post(
    "/tickets/{ticket_id}/close", response_model=TicketDetailResponse,
    summary="بستن تیکت با امتیاز رضایت",
)
async def close_my_ticket(
    ticket_id: str,
    body: TicketCloseRequest,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_my_ticket_or_404(db, current_user, ticket_id)
    await ticket_service.close_by_creator(db, ticket, body.satisfaction_rating)
    return await ticket_service.ticket_to_detail(db, ticket)


@router.post(
    "/tickets/{ticket_id}/reopen", response_model=TicketDetailResponse,
    summary="بازکردن دوباره‌ی تیکت بسته‌شده",
)
async def reopen_my_ticket(
    ticket_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    ticket = await _get_my_ticket_or_404(db, current_user, ticket_id)
    await ticket_service.reopen_ticket(db, ticket)
    return await ticket_service.ticket_to_detail(db, ticket)


# ─── Points Routes («امتیازات من») ─────────────────────────────────────────

@router.get("/points/summary", response_model=PointsSummaryResponse, summary="مجموع امتیاز من")
async def get_my_points_summary(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    total = await points_service.get_total_points_for_user(db, current_user.id)
    return PointsSummaryResponse(total_points=total)


@router.get("/points/history", response_model=PointsHistoryResponse, summary="تاریخچه‌ی امتیازهای من")
async def get_my_points_history(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await points_service.list_history_for_user(db, current_user.id, page=page, page_size=page_size)
    responses = [await points_service.entry_to_response(db, e) for e in items]
    return PointsHistoryResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/points/wallet", response_model=WalletResponse, summary="کیف‌پول کامل امتیاز من")
async def get_my_wallet(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    return await points_service.get_wallet_response(db, current_user.id)


# ─── Reward Marketplace («فروشگاه جایزه») ──────────────────────────────────

@router.get("/rewards", response_model=RewardListResponse, summary="کاتالوگ جایزه‌های قابل‌دسترس من")
async def list_my_rewards(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    category: str | None = Query(None),
):
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کاربر به هیچ سازمانی متصل نیست")
    items, total = await reward_service.list_rewards_for_catalog(
        db, current_user.org_id, page=page, page_size=page_size, search=search, category=category,
    )
    responses = [await reward_service.reward_to_response(db, r) for r in items]
    return RewardListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=reward_service.total_pages(total, page_size),
    )


# ─── Redemption Requests («درخواست‌های تبدیل امتیاز من») ───────────────────

async def _get_my_redemption_or_404(db: AsyncSession, current_user, redemption_id: str):
    redemption = await redemption_service.get_redemption(db, redemption_id)
    if not redemption or str(redemption.user_id) != str(current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "درخواست یافت نشد")
    return redemption


@router.post(
    "/redemptions", response_model=RedemptionResponse, status_code=status.HTTP_201_CREATED,
    summary="ثبت درخواست تبدیل امتیاز به جایزه",
)
async def create_my_redemption(
    body: RedemptionCreate,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    redemption = await redemption_service.create_redemption(db, current_user, body)
    return await redemption_service.redemption_to_response(db, redemption)


@router.get("/redemptions", response_model=RedemptionListResponse, summary="درخواست‌های تبدیل امتیاز من")
async def list_my_redemptions(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await redemption_service.list_redemptions_for_user(
        db, current_user.id, page=page, page_size=page_size, status_filter=status_filter,
    )
    responses = [await redemption_service.redemption_to_response(db, r) for r in items]
    return RedemptionListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=redemption_service.total_pages(total, page_size),
    )


@router.get("/redemptions/{redemption_id}", response_model=RedemptionResponse, summary="جزئیات یک درخواست تبدیل من")
async def get_my_redemption(
    redemption_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_my_redemption_or_404(db, current_user, redemption_id)
    return await redemption_service.redemption_to_response(db, redemption)


@router.patch("/redemptions/{redemption_id}/submit", response_model=RedemptionResponse, summary="ارسال درخواست Draft")
async def submit_my_redemption(
    redemption_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_my_redemption_or_404(db, current_user, redemption_id)
    updated = await redemption_service.submit_redemption(db, redemption, current_user)
    return await redemption_service.redemption_to_response(db, updated)


@router.patch("/redemptions/{redemption_id}/cancel", response_model=RedemptionResponse, summary="لغو درخواست تبدیل")
async def cancel_my_redemption(
    redemption_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    redemption = await _get_my_redemption_or_404(db, current_user, redemption_id)
    updated = await redemption_service.cancel_redemption(db, redemption, current_user)
    return await redemption_service.redemption_to_response(db, updated)


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
