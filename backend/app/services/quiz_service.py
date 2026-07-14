"""
Talentick — Quiz Service
==========================
CRUD کامل آزمون/سوال/گزینه (برای ادمین) + شرکت در آزمون و نمره‌دهی
خودکار (برای کارمند).

قوانین:
- هر query با org_id فیلتر می‌شود (از طریق quiz.org_id که قبلاً در
  router با enforce_org_scope تأیید شده) — Row-Level Security منطقی.
- QuizAttempt فقط INSERT می‌شود — هرگز UPDATE (طبق کامنت مدل).
- پاسخ صحیح (is_correct) و توضیح (explanation) هرگز قبل از ثبت attempt
  به کارمند نشان داده نمی‌شود — فقط در نتیجه‌ی بعد از ثبت.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError
from app.models.quiz import Question, QuestionOption, Quiz, QuizAttempt
from app.models.user import User
from app.schemas.quiz import (
    AnswerResult,
    QuestionAdminResponse,
    QuestionCreate,
    QuestionOptionAdminResponse,
    QuestionOptionTakeResponse,
    QuestionTakeResponse,
    QuestionUpdate,
    QuizAttemptAdminRow,
    QuizAttemptResult,
    QuizAttemptSubmit,
    QuizAttemptSummary,
    QuizCreate,
    QuizDetailResponse,
    QuizResponse,
    QuizTakeResponse,
    QuizUpdate,
)

# مهلت اضافه (ثانیه) برای در نظر گرفتن تأخیر شبکه هنگام بررسی محدودیت زمانی
_TIME_LIMIT_GRACE_SECONDS = 30


# ─── Helpers ──────────────────────────────────────────────────────────────

async def _get_questions_with_options(db: AsyncSession, quiz_id: uuid.UUID) -> list[Question]:
    result = await db.execute(
        select(Question)
        .where(Question.quiz_id == quiz_id)
        .options(selectinload(Question.options))
        .order_by(Question.order_index)
    )
    return list(result.scalars().unique().all())


async def _question_count(db: AsyncSession, quiz_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(Question).where(Question.quiz_id == quiz_id)
        )
    ).scalar_one()


def _validate_question_options(q_type: str, options: list) -> None:
    """
    اعتبارسنجی حداقلی گزینه‌ها بر اساس نوع سوال:
    - short_text: نیازی به گزینه ندارد (نمره‌دهی دستی — خارج از scope فعلی)
    - single_choice / true_false: دقیقاً یک گزینه صحیح
    - true_false: دقیقاً دو گزینه
    - multi_choice: حداقل یک گزینه صحیح
    """
    if q_type == "short_text":
        return
    if len(options) < 2:
        raise BadRequestError("سوالات چندگزینه‌ای/درست‌غلط حداقل به ۲ گزینه نیاز دارند")
    correct_count = sum(1 for o in options if o.is_correct)
    if q_type in ("single_choice", "true_false"):
        if correct_count != 1:
            raise BadRequestError("این نوع سوال باید دقیقاً یک گزینه‌ی صحیح داشته باشد")
        if q_type == "true_false" and len(options) != 2:
            raise BadRequestError("سوال درست/غلط باید دقیقاً ۲ گزینه داشته باشد")
    elif q_type == "multi_choice":
        if correct_count < 1:
            raise BadRequestError("سوال چندگزینه‌ای باید حداقل یک گزینه‌ی صحیح داشته باشد")


def question_to_admin_response(q: Question) -> QuestionAdminResponse:
    opts = sorted(q.options, key=lambda o: o.order_index)
    return QuestionAdminResponse(
        id=str(q.id),
        quiz_id=str(q.quiz_id),
        body=q.body,
        type=q.type,
        explanation=q.explanation,
        score=q.score,
        order_index=q.order_index,
        options=[
            QuestionOptionAdminResponse(
                id=str(o.id), body=o.body, is_correct=o.is_correct, order_index=o.order_index
            )
            for o in opts
        ],
    )


# ─── Quiz CRUD ──────────────────────────────────────────────────────────────

_SORTABLE_FIELDS = {
    "created_at": Quiz.created_at,
    "updated_at": Quiz.updated_at,
    "title": Quiz.title,
}


async def list_quizzes(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Quiz], int]:
    q = select(Quiz)
    if org_id is not None:
        q = q.where(Quiz.org_id == org_id)
    if search:
        q = q.where(Quiz.title.ilike(f"%{search.strip()}%"))
    if is_active is not None:
        q = q.where(Quiz.is_active.is_(is_active))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    sort_col = _SORTABLE_FIELDS.get(sort_by, Quiz.created_at)
    sort_col = sort_col.asc() if sort_order == "asc" else sort_col.desc()
    q = q.order_by(sort_col).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_quiz(db: AsyncSession, quiz_id: str) -> Quiz | None:
    try:
        qid = uuid.UUID(quiz_id)
    except ValueError:
        return None
    result = await db.execute(select(Quiz).where(Quiz.id == qid))
    return result.scalar_one_or_none()


async def create_quiz(
    db: AsyncSession, org_id: uuid.UUID, created_by: uuid.UUID, data: QuizCreate
) -> Quiz:
    quiz = Quiz(
        id=uuid.uuid4(),
        org_id=org_id,
        title=data.title,
        description=data.description,
        pass_score=data.pass_score,
        time_limit_min=data.time_limit_min,
        shuffle_questions=data.shuffle_questions,
        shuffle_options=data.shuffle_options,
        is_onboarding=data.is_onboarding,
        max_attempts=data.max_attempts,
        is_active=True,
        created_by=created_by,
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    return quiz


async def update_quiz(db: AsyncSession, quiz: Quiz, data: QuizUpdate) -> Quiz:
    payload = data.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(quiz, field, value)
    await db.commit()
    await db.refresh(quiz)
    return quiz


async def delete_quiz(db: AsyncSession, quiz: Quiz) -> None:
    await db.delete(quiz)
    await db.commit()


async def quiz_to_response(db: AsyncSession, quiz: Quiz) -> QuizResponse:
    created_by_name = None
    if quiz.created_by:
        creator = await db.get(User, quiz.created_by)
        created_by_name = creator.full_name if creator else None
    question_count = await _question_count(db, quiz.id)
    return QuizResponse(
        id=str(quiz.id),
        org_id=str(quiz.org_id),
        title=quiz.title,
        description=quiz.description,
        pass_score=quiz.pass_score,
        time_limit_min=quiz.time_limit_min,
        shuffle_questions=quiz.shuffle_questions,
        shuffle_options=quiz.shuffle_options,
        is_onboarding=quiz.is_onboarding,
        max_attempts=quiz.max_attempts,
        is_active=quiz.is_active,
        question_count=question_count,
        created_by=str(quiz.created_by) if quiz.created_by else None,
        created_by_name=created_by_name,
        created_at=quiz.created_at,
        updated_at=quiz.updated_at,
    )


async def quiz_to_detail(db: AsyncSession, quiz: Quiz) -> QuizDetailResponse:
    base = await quiz_to_response(db, quiz)
    questions = await _get_questions_with_options(db, quiz.id)
    return QuizDetailResponse(
        **base.model_dump(), questions=[question_to_admin_response(q) for q in questions]
    )


# ─── Question CRUD ─────────────────────────────────────────────────────────

async def add_question(db: AsyncSession, quiz: Quiz, data: QuestionCreate) -> Question:
    _validate_question_options(data.type, data.options)

    question = Question(
        id=uuid.uuid4(),
        org_id=quiz.org_id,
        quiz_id=quiz.id,
        body=data.body,
        type=data.type,
        explanation=data.explanation,
        score=data.score,
        order_index=data.order_index,
    )
    db.add(question)
    await db.flush()

    for opt in data.options:
        db.add(
            QuestionOption(
                id=uuid.uuid4(),
                question_id=question.id,
                body=opt.body,
                is_correct=opt.is_correct,
                order_index=opt.order_index,
            )
        )
    await db.commit()

    result = await db.execute(
        select(Question).where(Question.id == question.id).options(selectinload(Question.options))
    )
    return result.scalar_one()


async def get_question(db: AsyncSession, question_id: str) -> Question | None:
    try:
        qid = uuid.UUID(question_id)
    except ValueError:
        return None
    result = await db.execute(
        select(Question).where(Question.id == qid).options(selectinload(Question.options))
    )
    return result.scalar_one_or_none()


async def update_question(db: AsyncSession, question: Question, data: QuestionUpdate) -> Question:
    payload = data.model_dump(exclude_unset=True, exclude={"options"})
    for field, value in payload.items():
        setattr(question, field, value)

    final_type = data.type if data.type is not None else question.type

    if data.options is not None:
        _validate_question_options(final_type, data.options)
        await db.execute(
            QuestionOption.__table__.delete().where(QuestionOption.question_id == question.id)
        )
        for opt in data.options:
            db.add(
                QuestionOption(
                    id=uuid.uuid4(),
                    question_id=question.id,
                    body=opt.body,
                    is_correct=opt.is_correct,
                    order_index=opt.order_index,
                )
            )
    elif data.type is not None:
        # نوع سوال عوض شده ولی گزینه‌ی جدیدی نیامده — گزینه‌های فعلی را
        # با نوع جدید اعتبارسنجی می‌کنیم تا وضعیت نامعتبر (مثلاً
        # true_false با ۳ گزینه) ایجاد نشود.
        from app.schemas.quiz import QuestionOptionCreate

        current = [
            QuestionOptionCreate(body=o.body, is_correct=o.is_correct, order_index=o.order_index)
            for o in question.options
        ]
        _validate_question_options(final_type, current)

    await db.commit()
    result = await db.execute(
        select(Question).where(Question.id == question.id).options(selectinload(Question.options))
    )
    return result.scalar_one()


async def delete_question(db: AsyncSession, question: Question) -> None:
    await db.delete(question)
    await db.commit()


# ─── Take a Quiz (کارمند) ───────────────────────────────────────────────────

async def count_user_attempts(db: AsyncSession, user_id: uuid.UUID, quiz_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(QuizAttempt)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.quiz_id == quiz_id)
        )
    ).scalar_one()


async def get_quiz_for_taking(db: AsyncSession, quiz: Quiz, user: User) -> QuizTakeResponse:
    """
    نسخه‌ی امن سوالات برای کارمندی که می‌خواهد در آزمون شرکت کند —
    بدون is_correct و بدون explanation. اگر shuffle_questions/
    shuffle_options فعال باشد، ترتیب تصادفی اعمال می‌شود.
    """
    questions = await _get_questions_with_options(db, quiz.id)
    if quiz.shuffle_questions:
        questions = list(questions)
        random.shuffle(questions)

    take_questions: list[QuestionTakeResponse] = []
    for q in questions:
        opts = list(q.options)
        if quiz.shuffle_options:
            random.shuffle(opts)
        else:
            opts = sorted(opts, key=lambda o: o.order_index)
        take_questions.append(
            QuestionTakeResponse(
                id=str(q.id),
                body=q.body,
                type=q.type,
                score=q.score,
                order_index=q.order_index,
                options=[
                    QuestionOptionTakeResponse(id=str(o.id), body=o.body, order_index=o.order_index)
                    for o in opts
                ],
            )
        )

    attempts_used = await count_user_attempts(db, user.id, quiz.id)
    can_attempt = quiz.is_active and (
        quiz.max_attempts is None or attempts_used < quiz.max_attempts
    )

    return QuizTakeResponse(
        id=str(quiz.id),
        title=quiz.title,
        description=quiz.description,
        pass_score=quiz.pass_score,
        time_limit_min=quiz.time_limit_min,
        max_attempts=quiz.max_attempts,
        attempts_used=attempts_used,
        can_attempt=can_attempt,
        questions=take_questions,
    )


async def submit_attempt(
    db: AsyncSession, user: User, quiz: Quiz, data: QuizAttemptSubmit
) -> QuizAttempt:
    """
    یک attempt جدید ثبت می‌کند — نمره‌دهی خودکار برای single_choice/
    multi_choice/true_false (تطابق دقیق مجموعه‌ی گزینه‌های انتخابی با
    گزینه‌های صحیح). short_text نمره‌دهی دستی می‌خواهد (خارج از scope
    فعلی) — همیشه is_correct=None و score=0 می‌گیرد.

    خطاها: BadRequestError اگر تعداد دفعات مجاز پر شده یا مهلت زمانی
    گذشته باشد.
    """
    attempts_used = await count_user_attempts(db, user.id, quiz.id)
    if quiz.max_attempts is not None and attempts_used >= quiz.max_attempts:
        raise BadRequestError("تعداد دفعات مجاز شرکت در این آزمون به پایان رسیده است")

    now = datetime.now(timezone.utc)
    started_at = data.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if started_at > now:
        started_at = now
    duration_sec = max(0, int((now - started_at).total_seconds()))

    if quiz.time_limit_min is not None and duration_sec > quiz.time_limit_min * 60 + _TIME_LIMIT_GRACE_SECONDS:
        raise BadRequestError("زمان مجاز پاسخ‌گویی به این آزمون به پایان رسیده است")

    questions = await _get_questions_with_options(db, quiz.id)

    total_score = 0
    max_score = 0
    answers_json: dict[str, dict] = {}

    for q in questions:
        max_score += q.score
        submitted = data.answers.get(str(q.id))
        selected_ids = set(submitted.selected_option_ids) if submitted else set()
        text_answer = submitted.text_answer if submitted else None
        correct_option_ids = {str(o.id) for o in q.options if o.is_correct}

        if q.type == "short_text":
            is_correct = None
            score = 0
        else:
            is_correct = bool(correct_option_ids) and selected_ids == correct_option_ids
            score = q.score if is_correct else 0

        total_score += score
        answers_json[str(q.id)] = {
            "selected_option_ids": sorted(selected_ids),
            "text_answer": text_answer,
            "is_correct": is_correct,
            "score": score,
        }

    percentage = round((total_score / max_score) * 100, 2) if max_score else 0.0
    passed = percentage >= quiz.pass_score

    attempt = QuizAttempt(
        id=uuid.uuid4(),
        org_id=quiz.org_id,
        user_id=user.id,
        quiz_id=quiz.id,
        step_id=None,
        score=total_score,
        max_score=max_score,
        percentage=percentage,
        passed=passed,
        answers=answers_json,
        duration_sec=duration_sec,
        started_at=started_at,
        completed_at=now,
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def get_attempt(db: AsyncSession, attempt_id: str) -> QuizAttempt | None:
    try:
        aid = uuid.UUID(attempt_id)
    except ValueError:
        return None
    result = await db.execute(select(QuizAttempt).where(QuizAttempt.id == aid))
    return result.scalar_one_or_none()


async def list_my_attempts(
    db: AsyncSession, user_id: uuid.UUID, quiz_id: uuid.UUID
) -> list[QuizAttempt]:
    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.user_id == user_id, QuizAttempt.quiz_id == quiz_id)
        .order_by(QuizAttempt.completed_at.desc())
    )
    return list(result.scalars().all())


def attempt_to_summary(a: QuizAttempt) -> QuizAttemptSummary:
    """
    نگاشت دستی به‌جای QuizAttemptSummary.model_validate(a) — چون a.id از
    نوع uuid.UUID است و Pydantic v2 آن را به‌صورت خودکار به str تبدیل
    نمی‌کند (حتی با from_attributes=True) و ValidationError می‌دهد.
    """
    return QuizAttemptSummary(
        id=str(a.id),
        score=a.score,
        max_score=a.max_score,
        percentage=float(a.percentage),
        passed=a.passed,
        duration_sec=a.duration_sec,
        started_at=a.started_at,
        completed_at=a.completed_at,
    )


async def attempt_to_result(db: AsyncSession, attempt: QuizAttempt) -> QuizAttemptResult:
    quiz = await db.get(Quiz, attempt.quiz_id)
    questions = await _get_questions_with_options(db, attempt.quiz_id)
    q_map = {str(q.id): q for q in questions}

    answer_results: list[AnswerResult] = []
    for qid, ans in attempt.answers.items():
        q = q_map.get(qid)
        if not q:
            continue  # سوال بعداً حذف شده — از نتیجه صرف‌نظر می‌شود
        correct_ids = [str(o.id) for o in q.options if o.is_correct]
        answer_results.append(
            AnswerResult(
                question_id=qid,
                question_body=q.body,
                question_type=q.type,
                selected_option_ids=ans.get("selected_option_ids", []),
                text_answer=ans.get("text_answer"),
                is_correct=ans.get("is_correct"),
                score=ans.get("score", 0),
                max_score=q.score,
                explanation=q.explanation,
                correct_option_ids=correct_ids,
            )
        )
    answer_results.sort(key=lambda r: q_map[r.question_id].order_index if r.question_id in q_map else 0)

    return QuizAttemptResult(
        id=str(attempt.id),
        quiz_id=str(attempt.quiz_id),
        quiz_title=quiz.title if quiz else "",
        score=attempt.score,
        max_score=attempt.max_score,
        percentage=float(attempt.percentage),
        passed=attempt.passed,
        duration_sec=attempt.duration_sec,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        answers=answer_results,
    )


# ─── Attempts (گزارش ادمین) ────────────────────────────────────────────────

async def list_quiz_attempts_admin(
    db: AsyncSession,
    quiz: Quiz,
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: str | None = None,
    passed: bool | None = None,
) -> tuple[list[QuizAttemptAdminRow], int]:
    q = select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id)
    if user_id:
        q = q.where(QuizAttempt.user_id == uuid.UUID(user_id))
    if passed is not None:
        q = q.where(QuizAttempt.passed.is_(passed))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(QuizAttempt.completed_at.desc()).offset((page - 1) * page_size).limit(page_size)
    attempts = list((await db.execute(q)).scalars().all())

    user_ids = {a.user_id for a in attempts}
    users_map: dict[uuid.UUID, User] = {}
    if user_ids:
        rows = await db.execute(select(User).where(User.id.in_(user_ids)))
        users_map = {u.id: u for u in rows.scalars().all()}

    rows_out = [
        QuizAttemptAdminRow(
            id=str(a.id),
            user_id=str(a.user_id),
            user_full_name=users_map[a.user_id].full_name if a.user_id in users_map else "—",
            user_email=users_map[a.user_id].email if a.user_id in users_map else "—",
            score=a.score,
            max_score=a.max_score,
            percentage=float(a.percentage),
            passed=a.passed,
            duration_sec=a.duration_sec,
            started_at=a.started_at,
            completed_at=a.completed_at,
        )
        for a in attempts
    ]
    return rows_out, total
