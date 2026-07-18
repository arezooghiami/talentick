"""
Talentick — Onboarding Service
==================================
CRUD برنامه‌ی آشنایی (OnboardingProgram + ProgramStep) + ثبت‌نام کاربر
(UserProgramEnrollment) و پیشرفت هر مرحله (UserStepProgress).

منطق تکمیل: مرحله‌ی اجباری (is_required=True) فقط با status=completed
«انجام‌شده» حساب می‌شود؛ مرحله‌ی اختیاری با completed یا skipped. برنامه
کامل می‌شود وقتی همه‌ی مراحل اجباری completed باشند (مراحل اختیاری مانع
تکمیل نیستند).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.onboarding import (
    STEP_STATUSES,
    STEP_TYPES,
    OnboardingProgram,
    ProgramStep,
    UserProgramEnrollment,
    UserStepProgress,
)
from app.models.organization import Department, Organization
from app.models.quiz import Quiz
from app.models.user import VALID_ROLES, User
from app.schemas.onboarding import (
    EnrollmentResponse,
    MyEnrollmentDetailResponse,
    MyEnrollmentResponse,
    MyStepProgressResponse,
    OnboardingProgramCreate,
    OnboardingProgramDetailResponse,
    OnboardingProgramResponse,
    OnboardingProgramUpdate,
    ProgramStepCreate,
    ProgramStepResponse,
    ProgramStepUpdate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Validation ──────────────────────────────────────────────────────────────

async def _validate_step_payload(
    db: AsyncSession, org_id: uuid.UUID, step_type: str, content_id: str | None, quiz_id: str | None
) -> None:
    if step_type not in STEP_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نوع مرحله نامعتبر — مقادیر مجاز: {', '.join(STEP_TYPES)}")

    if step_type == "content":
        if not content_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای مرحله‌ی نوع «محتوا» انتخاب محتوا اجباری است")
        try:
            content = await db.get(Content, uuid.UUID(content_id))
        except ValueError:
            content = None
        if not content or str(content.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "محتوای انتخاب‌شده معتبر نیست")

    if step_type == "quiz":
        if not quiz_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای مرحله‌ی نوع «آزمون» انتخاب آزمون اجباری است")
        try:
            quiz = await db.get(Quiz, uuid.UUID(quiz_id))
        except ValueError:
            quiz = None
        if not quiz or str(quiz.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "آزمون انتخاب‌شده معتبر نیست")


async def _validate_program_payload(
    db: AsyncSession, org_id: uuid.UUID, target_roles: list[str] | None, target_dept_id: str | None
) -> None:
    if target_roles:
        invalid = [r for r in target_roles if r not in VALID_ROLES]
        if invalid:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نقش نامعتبر: {', '.join(invalid)}")
    if target_dept_id:
        try:
            dept = await db.get(Department, uuid.UUID(target_dept_id))
        except ValueError:
            dept = None
        if not dept or str(dept.org_id) != str(org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "واحد انتخاب‌شده معتبر نیست")


# ─── Mappers ────────────────────────────────────────────────────────────────

async def step_to_response(db: AsyncSession, step: ProgramStep) -> ProgramStepResponse:
    content_title = None
    if step.content_id:
        content = await db.get(Content, step.content_id)
        content_title = content.title if content else None
    quiz_title = None
    if step.quiz_id:
        quiz = await db.get(Quiz, step.quiz_id)
        quiz_title = quiz.title if quiz else None
    return ProgramStepResponse(
        id=str(step.id),
        program_id=str(step.program_id),
        title=step.title,
        description=step.description,
        type=step.type,
        content_id=str(step.content_id) if step.content_id else None,
        content_title=content_title,
        quiz_id=str(step.quiz_id) if step.quiz_id else None,
        quiz_title=quiz_title,
        is_required=step.is_required,
        order_index=step.order_index,
    )


async def program_to_response(db: AsyncSession, program: OnboardingProgram) -> OnboardingProgramResponse:
    org = await db.get(Organization, program.org_id)
    dept_name = None
    if program.target_dept_id:
        dept = await db.get(Department, program.target_dept_id)
        dept_name = dept.name if dept else None
    creator_name = None
    if program.created_by:
        creator = await db.get(User, program.created_by)
        creator_name = creator.full_name if creator else None

    step_count = (await db.execute(
        select(func.count()).select_from(ProgramStep).where(ProgramStep.program_id == program.id)
    )).scalar_one()
    enrollment_count = (await db.execute(
        select(func.count()).select_from(UserProgramEnrollment).where(
            UserProgramEnrollment.program_id == program.id
        )
    )).scalar_one()

    return OnboardingProgramResponse(
        id=str(program.id),
        org_id=str(program.org_id),
        org_name=org.name if org else None,
        name=program.name,
        description=program.description,
        target_roles=program.target_roles or [],
        target_dept_id=str(program.target_dept_id) if program.target_dept_id else None,
        target_dept_name=dept_name,
        is_default=program.is_default,
        deadline_days=program.deadline_days,
        is_active=program.is_active,
        step_count=step_count,
        enrollment_count=enrollment_count,
        created_by=str(program.created_by) if program.created_by else None,
        created_by_name=creator_name,
        created_at=program.created_at,
        updated_at=program.updated_at,
    )


async def program_to_detail(db: AsyncSession, program: OnboardingProgram) -> OnboardingProgramDetailResponse:
    base = await program_to_response(db, program)
    steps_result = await db.execute(
        select(ProgramStep).where(ProgramStep.program_id == program.id).order_by(ProgramStep.order_index)
    )
    steps = [await step_to_response(db, s) for s in steps_result.scalars().all()]
    return OnboardingProgramDetailResponse(**base.model_dump(), steps=steps)


# ─── Program CRUD ───────────────────────────────────────────────────────────

async def list_programs(
    db: AsyncSession,
    org_id: uuid.UUID | None,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> tuple[list[OnboardingProgram], int]:
    q = select(OnboardingProgram)
    if org_id is not None:
        q = q.where(OnboardingProgram.org_id == org_id)
    if search:
        q = q.where(OnboardingProgram.name.ilike(f"%{search.strip()}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(OnboardingProgram.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_program(db: AsyncSession, program_id: str) -> OnboardingProgram | None:
    try:
        pid = uuid.UUID(program_id)
    except ValueError:
        return None
    return await db.get(OnboardingProgram, pid)


async def create_program(
    db: AsyncSession, org_id: uuid.UUID, created_by: uuid.UUID, data: OnboardingProgramCreate
) -> OnboardingProgram:
    await _validate_program_payload(db, org_id, data.target_roles, data.target_dept_id)
    program = OnboardingProgram(
        id=uuid.uuid4(),
        org_id=org_id,
        name=data.name,
        description=data.description,
        target_roles=data.target_roles or [],
        target_dept_id=uuid.UUID(data.target_dept_id) if data.target_dept_id else None,
        is_default=data.is_default,
        deadline_days=data.deadline_days,
        is_active=data.is_active,
        created_by=created_by,
    )
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return program


async def update_program(
    db: AsyncSession, program: OnboardingProgram, data: OnboardingProgramUpdate
) -> OnboardingProgram:
    payload = data.model_dump(exclude_unset=True)

    target_roles = payload.get("target_roles", program.target_roles)
    target_dept_id = payload.get("target_dept_id", "__unset__")
    resolved_dept_id = program.target_dept_id
    if target_dept_id != "__unset__":
        resolved_dept_id = uuid.UUID(target_dept_id) if target_dept_id else None
    await _validate_program_payload(
        db, program.org_id, target_roles, str(resolved_dept_id) if resolved_dept_id else None
    )

    for field in ("name", "description", "is_default", "deadline_days", "is_active"):
        if field in payload:
            setattr(program, field, payload[field])
    if "target_roles" in payload:
        program.target_roles = payload["target_roles"] or []
    if "target_dept_id" in payload:
        program.target_dept_id = resolved_dept_id

    await db.commit()
    await db.refresh(program)
    return program


async def delete_program(db: AsyncSession, program: OnboardingProgram) -> None:
    await db.delete(program)
    await db.commit()


# ─── Step CRUD ──────────────────────────────────────────────────────────────

async def add_step(db: AsyncSession, program: OnboardingProgram, data: ProgramStepCreate) -> ProgramStep:
    await _validate_step_payload(db, program.org_id, data.type, data.content_id, data.quiz_id)
    next_index = (await db.execute(
        select(func.count()).select_from(ProgramStep).where(ProgramStep.program_id == program.id)
    )).scalar_one()
    step = ProgramStep(
        id=uuid.uuid4(),
        org_id=program.org_id,
        program_id=program.id,
        title=data.title,
        description=data.description,
        type=data.type,
        content_id=uuid.UUID(data.content_id) if data.content_id else None,
        quiz_id=uuid.UUID(data.quiz_id) if data.quiz_id else None,
        is_required=data.is_required,
        order_index=data.order_index or next_index,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def get_step(db: AsyncSession, step_id: str) -> ProgramStep | None:
    try:
        sid = uuid.UUID(step_id)
    except ValueError:
        return None
    return await db.get(ProgramStep, sid)


async def update_step(db: AsyncSession, step: ProgramStep, data: ProgramStepUpdate) -> ProgramStep:
    payload = data.model_dump(exclude_unset=True)
    new_type = payload.get("type", step.type)
    new_content_id = payload.get("content_id", str(step.content_id) if step.content_id else None)
    new_quiz_id = payload.get("quiz_id", str(step.quiz_id) if step.quiz_id else None)
    if "type" in payload or "content_id" in payload or "quiz_id" in payload:
        await _validate_step_payload(db, step.org_id, new_type, new_content_id, new_quiz_id)

    for field in ("title", "description", "type", "is_required", "order_index"):
        if field in payload:
            setattr(step, field, payload[field])
    if "content_id" in payload:
        step.content_id = uuid.UUID(payload["content_id"]) if payload["content_id"] else None
    if "quiz_id" in payload:
        step.quiz_id = uuid.UUID(payload["quiz_id"]) if payload["quiz_id"] else None

    await db.commit()
    await db.refresh(step)
    return step


async def delete_step(db: AsyncSession, step: ProgramStep) -> None:
    await db.delete(step)
    await db.commit()


# ─── Targeting / Auto-Enrollment ────────────────────────────────────────────

def is_program_visible_to_user(program: OnboardingProgram, user: User) -> bool:
    """
    فیلتر نقش/واحد — هر دو بعد AND هستند (نه OR مثل Content/Announcement)،
    چون OnboardingProgram به‌جای جدول targets جداگانه، دو ستون مستقیم روی
    خودش دارد: یعنی «محدودتر کردن» مخاطب، نه افزودن گزینه‌های جایگزین.
    خالی‌بودن یک بعد یعنی آن بعد محدودیتی اعمال نمی‌کند.
    """
    if program.target_roles and user.role not in program.target_roles:
        return False
    if program.target_dept_id and str(user.dept_id) != str(program.target_dept_id):
        return False
    return True


async def auto_enroll_new_user(db: AsyncSession, user: User) -> None:
    """
    وقتی کاربر جدید ساخته می‌شود، در تمام برنامه‌های is_default و فعال
    سازمانش که برایش قابل‌مشاهده‌اند (نقش/واحد) خودکار ثبت‌نام می‌شود.

    غیرحیاتی است — اگر خطا بدهد نباید ساخت کاربر را متوقف کند (به همین
    دلیل در router با try/except فراخوانی می‌شود).
    """
    if user.org_id is None:
        return
    result = await db.execute(
        select(OnboardingProgram).where(
            OnboardingProgram.org_id == user.org_id,
            OnboardingProgram.is_active.is_(True),
            OnboardingProgram.is_default.is_(True),
        )
    )
    for program in result.scalars().all():
        if is_program_visible_to_user(program, user):
            await enroll_user(db, program, user, enrolled_by=None)


async def enroll_user(
    db: AsyncSession, program: OnboardingProgram, user: User, enrolled_by: uuid.UUID | None
) -> UserProgramEnrollment:
    """ثبت‌نام یک کاربر در یک برنامه — idempotent (اگر از قبل ثبت‌نام باشد، همان را برمی‌گرداند)."""
    existing = (await db.execute(
        select(UserProgramEnrollment).where(
            UserProgramEnrollment.program_id == program.id,
            UserProgramEnrollment.user_id == user.id,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    now = _now()
    enrollment = UserProgramEnrollment(
        id=uuid.uuid4(),
        org_id=program.org_id,
        user_id=user.id,
        program_id=program.id,
        enrolled_by=enrolled_by,
        enrolled_at=now,
        deadline_at=now + timedelta(days=program.deadline_days) if program.deadline_days else None,
        progress_pct=0,
    )
    db.add(enrollment)
    await db.flush()

    steps_result = await db.execute(select(ProgramStep).where(ProgramStep.program_id == program.id))
    for step in steps_result.scalars().all():
        db.add(UserStepProgress(
            id=uuid.uuid4(),
            org_id=program.org_id,
            user_id=user.id,
            step_id=step.id,
            enrollment_id=enrollment.id,
            status="not_started",
        ))
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


# ─── Enrollment — نمای مدیریتی (پیگیری پیشرفت کارکنان) ────────────────────

async def list_enrollments(
    db: AsyncSession, program: OnboardingProgram, *, page: int = 1, page_size: int = 20
) -> tuple[list[EnrollmentResponse], int]:
    """
    نمای مدیریتی: چه کسانی ثبت‌نام‌اند و چقدر پیش رفته‌اند — با کوئری‌های
    batched (نه یک کوئری جدا به ازای هر ثبت‌نام) تا برای برنامه‌های
    پرجمعیت هم کند نشود.
    """
    count_q = select(func.count()).select_from(UserProgramEnrollment).where(
        UserProgramEnrollment.program_id == program.id
    )
    total = (await db.execute(count_q)).scalar_one()

    q = (
        select(UserProgramEnrollment, User)
        .join(User, User.id == UserProgramEnrollment.user_id)
        .where(UserProgramEnrollment.program_id == program.id)
        .order_by(UserProgramEnrollment.enrolled_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(q)).all()
    if not rows:
        return [], total

    enrollment_ids = [e.id for e, _ in rows]
    total_steps = (await db.execute(
        select(func.count()).select_from(ProgramStep).where(ProgramStep.program_id == program.id)
    )).scalar_one()

    counts_result = await db.execute(
        select(
            UserStepProgress.enrollment_id,
            func.count().filter(UserStepProgress.status.in_(("completed", "skipped"))),
        )
        .where(UserStepProgress.enrollment_id.in_(enrollment_ids))
        .group_by(UserStepProgress.enrollment_id)
    )
    completed_map = {eid: cnt for eid, cnt in counts_result.all()}

    return [
        EnrollmentResponse(
            id=str(e.id),
            program_id=str(e.program_id),
            user_id=str(e.user_id),
            user_name=u.full_name,
            user_email=u.email,
            enrolled_at=e.enrolled_at,
            deadline_at=e.deadline_at,
            completed_at=e.completed_at,
            progress_pct=e.progress_pct,
            steps_total=total_steps,
            steps_completed=completed_map.get(e.id, 0),
        )
        for e, u in rows
    ], total


# ─── Enrollment — نمای شخصی کارمند («مسیر آنبوردینگ من») ──────────────────

async def get_my_enrollments(db: AsyncSession, user: User) -> list[MyEnrollmentResponse]:
    rows = (await db.execute(
        select(UserProgramEnrollment, OnboardingProgram)
        .join(OnboardingProgram, OnboardingProgram.id == UserProgramEnrollment.program_id)
        .where(UserProgramEnrollment.user_id == user.id)
        .order_by(UserProgramEnrollment.completed_at.is_not(None), UserProgramEnrollment.enrolled_at.desc())
    )).all()
    if not rows:
        return []

    enrollment_ids = [e.id for e, _ in rows]
    steps_total_result = await db.execute(
        select(ProgramStep.program_id, func.count())
        .where(ProgramStep.program_id.in_([p.id for _, p in rows]))
        .group_by(ProgramStep.program_id)
    )
    steps_total_map = {pid: cnt for pid, cnt in steps_total_result.all()}

    completed_result = await db.execute(
        select(
            UserStepProgress.enrollment_id,
            func.count().filter(UserStepProgress.status.in_(("completed", "skipped"))),
        )
        .where(UserStepProgress.enrollment_id.in_(enrollment_ids))
        .group_by(UserStepProgress.enrollment_id)
    )
    completed_map = {eid: cnt for eid, cnt in completed_result.all()}

    return [
        MyEnrollmentResponse(
            enrollment_id=str(e.id),
            program_id=str(p.id),
            program_name=p.name,
            program_description=p.description,
            enrolled_at=e.enrolled_at,
            deadline_at=e.deadline_at,
            completed_at=e.completed_at,
            progress_pct=e.progress_pct,
            steps_total=steps_total_map.get(p.id, 0),
            steps_completed=completed_map.get(e.id, 0),
        )
        for e, p in rows
    ]


async def get_enrollment_for_user(db: AsyncSession, user: User, enrollment_id: str) -> UserProgramEnrollment | None:
    try:
        eid = uuid.UUID(enrollment_id)
    except ValueError:
        return None
    enrollment = await db.get(UserProgramEnrollment, eid)
    if not enrollment or str(enrollment.user_id) != str(user.id):
        return None
    return enrollment


async def get_my_enrollment_detail(db: AsyncSession, enrollment: UserProgramEnrollment) -> MyEnrollmentDetailResponse:
    program = await db.get(OnboardingProgram, enrollment.program_id)
    steps_result = await db.execute(
        select(ProgramStep).where(ProgramStep.program_id == enrollment.program_id).order_by(ProgramStep.order_index)
    )
    steps = steps_result.scalars().all()

    progress_result = await db.execute(
        select(UserStepProgress).where(UserStepProgress.enrollment_id == enrollment.id)
    )
    progress_map = {p.step_id: p for p in progress_result.scalars().all()}

    step_responses = []
    for step in steps:
        p = progress_map.get(step.id)
        content_title = None
        if step.content_id:
            content = await db.get(Content, step.content_id)
            content_title = content.title if content else None
        quiz_title = None
        if step.quiz_id:
            quiz = await db.get(Quiz, step.quiz_id)
            quiz_title = quiz.title if quiz else None
        step_responses.append(MyStepProgressResponse(
            step_id=str(step.id),
            title=step.title,
            description=step.description,
            type=step.type,
            content_id=str(step.content_id) if step.content_id else None,
            content_title=content_title,
            quiz_id=str(step.quiz_id) if step.quiz_id else None,
            quiz_title=quiz_title,
            is_required=step.is_required,
            order_index=step.order_index,
            status=p.status if p else "not_started",
            notes=p.notes if p else None,
            completed_at=p.completed_at if p else None,
        ))

    return MyEnrollmentDetailResponse(
        enrollment_id=str(enrollment.id),
        program_id=str(program.id),
        program_name=program.name,
        program_description=program.description,
        enrolled_at=enrollment.enrolled_at,
        deadline_at=enrollment.deadline_at,
        completed_at=enrollment.completed_at,
        progress_pct=enrollment.progress_pct,
        steps_total=len(steps),
        steps_completed=sum(1 for s in step_responses if s.status in ("completed", "skipped")),
        steps=step_responses,
    )


async def get_step_progress_for_user(db: AsyncSession, user: User, step_id: str) -> UserStepProgress | None:
    try:
        sid = uuid.UUID(step_id)
    except ValueError:
        return None
    return (await db.execute(
        select(UserStepProgress).where(
            UserStepProgress.step_id == sid, UserStepProgress.user_id == user.id
        )
    )).scalar_one_or_none()


async def set_step_status(
    db: AsyncSession, step_progress: UserStepProgress, new_status: str, notes: str | None = None
) -> UserStepProgress:
    if new_status not in STEP_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "وضعیت نامعتبر است")

    step = await db.get(ProgramStep, step_progress.step_id)
    if new_status == "skipped" and step and step.is_required:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مراحل اجباری را نمی‌توان رد کرد")

    step_progress.status = new_status
    if notes is not None:
        step_progress.notes = notes
    step_progress.completed_at = _now() if new_status in ("completed", "skipped") else None
    await db.flush()

    await _recalculate_enrollment_progress(db, step_progress.enrollment_id)
    await db.commit()
    await db.refresh(step_progress)
    return step_progress


async def _recalculate_enrollment_progress(db: AsyncSession, enrollment_id: uuid.UUID) -> None:
    """
    پیشرفت ثبت‌نام را از روی وضعیت مراحل بازمحاسبه می‌کند.

    - progress_pct = درصد مراحلی که «انجام‌شده» حساب می‌شوند از کل مراحل
      (اجباری فقط با completed، اختیاری با completed یا skipped).
    - completed_at ست می‌شود وقتی همه‌ی مراحل اجباری completed باشند —
      مراحل اختیاری مانع تکمیل برنامه نیستند.
    """
    enrollment = await db.get(UserProgramEnrollment, enrollment_id)
    if not enrollment:
        return

    steps_result = await db.execute(
        select(ProgramStep.id, ProgramStep.is_required).where(ProgramStep.program_id == enrollment.program_id)
    )
    steps = steps_result.all()
    total = len(steps)
    if total == 0:
        enrollment.progress_pct = 0
        await db.flush()
        return

    progress_result = await db.execute(
        select(UserStepProgress.step_id, UserStepProgress.status).where(
            UserStepProgress.enrollment_id == enrollment_id
        )
    )
    status_map = {sid: st for sid, st in progress_result.all()}

    done_count = 0
    required_incomplete = False
    for step_id, is_required in steps:
        step_status = status_map.get(step_id, "not_started")
        if is_required:
            if step_status == "completed":
                done_count += 1
            else:
                required_incomplete = True
        else:
            if step_status in ("completed", "skipped"):
                done_count += 1

    # progress_pct صادقانه سهم واقعی مراحل انجام‌شده (اجباری + اختیاری) از
    # کل مراحل است — لزوماً با «تکمیل برنامه» یکی نیست: ممکن است همه‌ی
    # مراحل اجباری تمام شده باشند (completed_at ست می‌شود) درحالی‌که هنوز
    # یک مرحله‌ی اختیاری باقی مانده و progress_pct به ۱۰۰ نرسیده باشد.
    enrollment.progress_pct = int(round(100 * done_count / total))
    if not required_incomplete:
        if enrollment.completed_at is None:
            enrollment.completed_at = _now()
    else:
        enrollment.completed_at = None

    await db.flush()
