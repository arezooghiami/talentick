"""
Talentick — Quizzes Router
============================
مدیریت آزمون (Quiz/Question/QuestionOption) — برای ادمین سازمان — به
علاوه‌ی گزارش تلاش‌های کاربران روی هر آزمون.

Routes:
  GET    /api/quizzes/                      → لیست آزمون‌ها (فیلتر/جستجو/صفحه‌بندی)
  POST   /api/quizzes/                      → ساخت آزمون جدید
  GET    /api/quizzes/{id}                  → جزئیات + سوالات (شامل پاسخ صحیح)
  PATCH  /api/quizzes/{id}                  → ویرایش آزمون
  DELETE /api/quizzes/{id}                  → حذف آزمون
  POST   /api/quizzes/{id}/questions        → افزودن سوال (+ گزینه‌ها)
  PATCH  /api/quizzes/questions/{qid}       → ویرایش سوال
  DELETE /api/quizzes/questions/{qid}       → حذف سوال
  GET    /api/quizzes/{id}/attempts         → گزارش تلاش‌های کاربران روی این آزمون

مسیرهای «شرکت در آزمون» برای کارمند در routers/me.py هستند
(GET/POST /api/me/quizzes/{id}, ...) — چون آن پرتال کاربر عادی است، نه
پنل مدیریت.

دسترسی: ساخت/ویرایش/حذف/گزارش فقط OrgAdmin به بالا (سازمان خودشان).
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin
from app.dependencies import enforce_org_scope
from app.models.quiz import Quiz
from app.models.user import User
from app.schemas.quiz import (
    QUESTION_TYPES,
    QuestionAdminResponse,
    QuestionCreate,
    QuestionUpdate,
    QuizAttemptListResponse,
    QuizCreate,
    QuizDetailResponse,
    QuizListResponse,
    QuizUpdate,
)
from app.services import quiz_service

router = APIRouter(prefix="/api/quizzes", tags=["Quizzes"])


# ─── Helpers ──────────────────────────────────────────────────────────────

def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID | None:
    """
    super_admin: با org_id فیلتر می‌کند، یا اگر ندهد None برمی‌گردد (یعنی
    همه‌ی سازمان‌ها — برای مدیریت کلی پلتفرم).
    سایر نقش‌ها همیشه محدود به سازمان خودشان هستند.
    """
    if current_user.role == "super_admin":
        if org_id:
            try:
                return uuid.UUID(org_id)
            except ValueError:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
        return None
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


def _validate_type(value: str) -> None:
    if value not in QUESTION_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نوع سوال نامعتبر است — مقادیر مجاز: {', '.join(QUESTION_TYPES)}",
        )


async def _get_quiz_or_404(db: AsyncSession, quiz_id: str) -> Quiz:
    quiz = await quiz_service.get_quiz(db, quiz_id)
    if not quiz:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "آزمون یافت نشد")
    return quiz


# ─── Quiz Routes ─────────────────────────────────────────────────────────

@router.get("/", response_model=QuizListResponse, summary="لیست آزمون‌های سازمان")
async def list_quizzes(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = همه سازمان‌ها"),
    sort_by: str = Query("created_at", description="created_at | updated_at | title"),
    sort_order: str = Query("desc", description="asc | desc"),
) -> QuizListResponse:
    target_org_id = _resolve_org_id(current_user, org_id)
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "sort_order باید asc یا desc باشد")

    items, total = await quiz_service.list_quizzes(
        db, target_org_id, page=page, page_size=page_size,
        search=search, is_active=is_active, sort_by=sort_by, sort_order=sort_order,
    )
    responses = [await quiz_service.quiz_to_response(db, q) for q in items]
    return QuizListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/", response_model=QuizDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ساخت آزمون جدید",
)
async def create_quiz(
    body: QuizCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> QuizDetailResponse:
    org_id = current_user.org_id
    if current_user.role == "super_admin" and body.org_id:
        org_id = uuid.UUID(body.org_id)
    if org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")

    quiz = await quiz_service.create_quiz(db, org_id, current_user.id, body)
    return await quiz_service.quiz_to_detail(db, quiz)


@router.get("/{quiz_id}", response_model=QuizDetailResponse, summary="جزئیات آزمون (شامل پاسخ صحیح)")
async def get_quiz(
    quiz_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> QuizDetailResponse:
    quiz = await _get_quiz_or_404(db, quiz_id)
    enforce_org_scope(current_user, quiz.org_id)
    return await quiz_service.quiz_to_detail(db, quiz)


@router.patch("/{quiz_id}", response_model=QuizDetailResponse, summary="ویرایش آزمون")
async def update_quiz(
    quiz_id: str,
    body: QuizUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> QuizDetailResponse:
    quiz = await _get_quiz_or_404(db, quiz_id)
    enforce_org_scope(current_user, quiz.org_id)
    updated = await quiz_service.update_quiz(db, quiz, body)
    return await quiz_service.quiz_to_detail(db, updated)


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف آزمون")
async def delete_quiz(
    quiz_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> None:
    quiz = await _get_quiz_or_404(db, quiz_id)
    enforce_org_scope(current_user, quiz.org_id)
    await quiz_service.delete_quiz(db, quiz)


# ─── Question Routes ────────────────────────────────────────────────────────

@router.post(
    "/{quiz_id}/questions", response_model=QuestionAdminResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن سوال به آزمون",
    description="""
    برای single_choice/true_false دقیقاً یک گزینه‌ی صحیح، برای
    multi_choice حداقل یک گزینه‌ی صحیح، برای true_false دقیقاً ۲ گزینه
    لازم است. short_text نیازی به گزینه ندارد (نمره‌دهی دستی — خارج از
    scope فعلی، همیشه امتیاز ۰ می‌گیرد).
    """,
    responses={400: {"description": "نوع سوال یا تعداد/ترکیب گزینه‌های صحیح نامعتبر است"}},
)
async def add_question(
    quiz_id: str,
    body: QuestionCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> QuestionAdminResponse:
    quiz = await _get_quiz_or_404(db, quiz_id)
    enforce_org_scope(current_user, quiz.org_id)
    _validate_type(body.type)

    question = await quiz_service.add_question(db, quiz, body)
    return quiz_service.question_to_admin_response(question)


@router.patch(
    "/questions/{question_id}", response_model=QuestionAdminResponse, summary="ویرایش سوال",
    responses={400: {"description": "نوع سوال یا تعداد/ترکیب گزینه‌های صحیح نامعتبر است"}},
)
async def update_question(
    question_id: str,
    body: QuestionUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> QuestionAdminResponse:
    question = await quiz_service.get_question(db, question_id)
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سوال یافت نشد")
    enforce_org_scope(current_user, question.org_id)
    if body.type:
        _validate_type(body.type)

    updated = await quiz_service.update_question(db, question, body)
    return quiz_service.question_to_admin_response(updated)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف سوال")
async def delete_question(
    question_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
) -> None:
    question = await quiz_service.get_question(db, question_id)
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سوال یافت نشد")
    enforce_org_scope(current_user, question.org_id)
    await quiz_service.delete_question(db, question)


# ─── Attempts (گزارش) ────────────────────────────────────────────────────────

@router.get(
    "/{quiz_id}/attempts", response_model=QuizAttemptListResponse,
    summary="گزارش تلاش‌های کاربران روی این آزمون",
)
async def list_quiz_attempts(
    quiz_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str | None = Query(None),
    passed: bool | None = Query(None),
) -> QuizAttemptListResponse:
    quiz = await _get_quiz_or_404(db, quiz_id)
    enforce_org_scope(current_user, quiz.org_id)

    items, total = await quiz_service.list_quiz_attempts_admin(
        db, quiz, page=page, page_size=page_size, user_id=user_id, passed=passed,
    )
    return QuizAttemptListResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )
