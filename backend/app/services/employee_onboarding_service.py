"""
Talentick — Employee Onboarding Service (کاتالوگ مدارک + وضعیت کاربر)
==========================================================================
بعد از بازطراحی مشترک با ماژول آنبوردینگ، «مسیر ورود کارمند جدید» دیگر
یک Config/Progress جداگانه ندارد — خودش یک
app.models.onboarding.OnboardingProgram با purpose="employee_onboarding"
است (CRUD مسیر/مرحله در services/onboarding_service.py است، نه اینجا).

این فایل فقط مسئول دو چیز است:
    ۱) کاتالوگ مدارک سازمان (EmployeeDocumentType) — CRUD مدیریتی
    ۲) ثبت مدرک/مقدار توسط کارمند (EmployeeDocumentSubmission) — تأیید
       خودکار در لحظه‌ی ثبت + sync مرحله‌ی document_upload مرتبط (از
       طریق onboarding_service.sync_document_upload_steps_for_user)

Gate (آیا کاربر مسدود است) در onboarding_service.get_employee_onboarding_gate_status
است — مستقیماً از dependencies.py صدا زده می‌شود، نه از این فایل.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ALLOWED_EXTENSIONS as GLOBAL_ALLOWED_EXTENSIONS
from app.core.storage import MAX_FILE_SIZE_MB as GLOBAL_MAX_FILE_SIZE_MB
from app.models.employee_onboarding import (
    DOCUMENT_INPUT_TYPES,
    EmployeeDocumentSubmission,
    EmployeeDocumentType,
)
from app.models.onboarding import OnboardingProgram, ProgramStep, UserProgramEnrollment, UserStepProgress
from app.models.user import User
from app.schemas.employee_onboarding import (
    DocumentsStatus,
    DocumentSubmissionResponse,
    DocumentTypeStatusResponse,
    EmployeeDocumentTypeCreate,
    EmployeeDocumentTypeResponse,
    EmployeeDocumentTypeUpdate,
    EmployeeOnboardingEnrollmentSummary,
    EmployeeOnboardingStatusResponse,
)
from app.services import onboarding_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Document Types (کاتالوگ مدارک سازمان) ──────────────────────────────────

def _validate_extensions(extensions: list[str]) -> None:
    invalid = [e for e in extensions if e.lower() not in GLOBAL_ALLOWED_EXTENSIONS]
    if invalid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"فرمت‌های نامعتبر: {', '.join(invalid)} — فرمت‌های مجاز سراسری: {', '.join(sorted(GLOBAL_ALLOWED_EXTENSIONS))}",
        )


def _validate_input_type(input_type: str) -> None:
    if input_type not in DOCUMENT_INPUT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"نوع ورودی نامعتبر — مقادیر مجاز: {', '.join(DOCUMENT_INPUT_TYPES)}",
        )


async def list_document_types(
    db: AsyncSession, org_id: uuid.UUID, *, active_only: bool = False
) -> list[EmployeeDocumentType]:
    q = select(EmployeeDocumentType).where(EmployeeDocumentType.org_id == org_id)
    if active_only:
        q = q.where(EmployeeDocumentType.is_active.is_(True))
    q = q.order_by(EmployeeDocumentType.order_index, EmployeeDocumentType.created_at)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_document_type(db: AsyncSession, document_type_id: str) -> EmployeeDocumentType | None:
    try:
        did = uuid.UUID(document_type_id)
    except ValueError:
        return None
    return await db.get(EmployeeDocumentType, did)


async def create_document_type(
    db: AsyncSession, org_id: uuid.UUID, data: EmployeeDocumentTypeCreate
) -> EmployeeDocumentType:
    _validate_input_type(data.input_type)
    extensions: list[str] = []
    max_size_mb = None
    template_file_url = None
    if data.input_type == "file":
        extensions = [e.lower().lstrip(".") for e in data.allowed_extensions]
        _validate_extensions(extensions)
        max_size_mb = data.max_size_mb
        template_file_url = data.template_file_url

    doc_type = EmployeeDocumentType(
        id=uuid.uuid4(),
        org_id=org_id,
        name=data.name,
        description=data.description,
        input_type=data.input_type,
        is_required=data.is_required,
        allowed_extensions=extensions,
        max_size_mb=max_size_mb,
        template_file_url=template_file_url,
        order_index=data.order_index,
        is_active=data.is_active,
    )
    db.add(doc_type)
    await db.commit()
    await db.refresh(doc_type)
    return doc_type


async def update_document_type(
    db: AsyncSession, doc_type: EmployeeDocumentType, data: EmployeeDocumentTypeUpdate
) -> EmployeeDocumentType:
    payload = data.model_dump(exclude_unset=True)
    new_input_type = payload.get("input_type", doc_type.input_type)
    if "input_type" in payload:
        _validate_input_type(new_input_type)
    if new_input_type == "text":
        # اگر به text تغییر کرد، فیلدهای مختص file بی‌معنا می‌شوند — پاک می‌شوند
        payload.setdefault("allowed_extensions", [])
        payload.setdefault("max_size_mb", None)
        payload.setdefault("template_file_url", None)
    if "allowed_extensions" in payload and payload["allowed_extensions"] is not None:
        payload["allowed_extensions"] = [e.lower().lstrip(".") for e in payload["allowed_extensions"]]
        if new_input_type == "file":
            _validate_extensions(payload["allowed_extensions"])
    for field, value in payload.items():
        setattr(doc_type, field, value)
    await db.commit()
    await db.refresh(doc_type)

    # ممکن است required/is_active تغییر کرده باشد — مراحل document_upload
    # همه‌ی کاربرانی که مدرکی برای این قلم ثبت کرده‌اند باید بازمحاسبه شوند.
    try:
        user_ids_result = await db.execute(
            select(EmployeeDocumentSubmission.user_id).where(
                EmployeeDocumentSubmission.document_type_id == doc_type.id
            ).distinct()
        )
        for (user_id,) in user_ids_result.all():
            await onboarding_service.sync_document_upload_steps_for_user(db, user_id)
        await db.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("sync مراحل document_upload بعد از ویرایش قلم %s ناموفق بود", doc_type.id)

    return doc_type


async def delete_document_type(db: AsyncSession, doc_type: EmployeeDocumentType) -> None:
    await db.delete(doc_type)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این نوع مدرک قبلاً توسط کارکنان ثبت شده — برای حفظ سابقه‌ی مدارک نمی‌توان آن را حذف کرد. "
            "به‌جای حذف، آن را غیرفعال (is_active=false) کنید.",
        ) from exc


async def document_type_to_response(db: AsyncSession, doc_type: EmployeeDocumentType) -> EmployeeDocumentTypeResponse:
    submission_count = (await db.execute(
        select(func.count()).select_from(EmployeeDocumentSubmission).where(
            EmployeeDocumentSubmission.document_type_id == doc_type.id
        )
    )).scalar_one()
    return EmployeeDocumentTypeResponse(
        id=str(doc_type.id),
        org_id=str(doc_type.org_id),
        name=doc_type.name,
        description=doc_type.description,
        input_type=doc_type.input_type,
        is_required=doc_type.is_required,
        allowed_extensions=doc_type.allowed_extensions or [],
        max_size_mb=doc_type.max_size_mb,
        template_file_url=doc_type.template_file_url,
        order_index=doc_type.order_index,
        is_active=doc_type.is_active,
        submission_count=submission_count,
        created_at=doc_type.created_at,
        updated_at=doc_type.updated_at,
    )


# ─── Document Submissions ────────────────────────────────────────────────────

async def get_submission(db: AsyncSession, user_id: uuid.UUID, document_type_id: uuid.UUID) -> EmployeeDocumentSubmission | None:
    return (await db.execute(
        select(EmployeeDocumentSubmission).where(
            EmployeeDocumentSubmission.user_id == user_id,
            EmployeeDocumentSubmission.document_type_id == document_type_id,
        )
    )).scalar_one_or_none()


async def _after_submission_change(db: AsyncSession, user_id: uuid.UUID) -> None:
    """هر مرحله‌ی document_upload این کاربر (در هر Program‌ای) را بازمحاسبه می‌کند."""
    await onboarding_service.sync_document_upload_steps_for_user(db, user_id)
    await db.commit()


async def submit_document(
    db: AsyncSession, user: User, document_type: EmployeeDocumentType, upload_result: dict
) -> EmployeeDocumentSubmission:
    """
    ثبت مدرک آپلودشده (فقط input_type=file) — تأیید خودکار
    (status="approved") در همین لحظه. اگر کاربر قبلاً برای همین
    document_type مدرکی فرستاده بود، همان سطر overwrite می‌شود (بدون
    نگه‌داشتن نسخه‌های قبلی).
    """
    if document_type.input_type != "file":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{document_type.name}» از نوع آپلود فایل نیست — از endpoint متنی استفاده کنید")
    filename = upload_result.get("filename") or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if document_type.allowed_extensions and ext not in document_type.allowed_extensions:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"فرمت فایل برای «{document_type.name}» مجاز نیست — فرمت‌های مجاز: {', '.join(document_type.allowed_extensions)}",
        )
    size_mb = (upload_result.get("size") or 0) / (1024 * 1024)
    max_mb = document_type.max_size_mb or GLOBAL_MAX_FILE_SIZE_MB
    if size_mb > max_mb:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"حجم فایل بیش از حد مجاز است (حداکثر {max_mb}MB)")

    existing = await get_submission(db, user.id, document_type.id)
    now = _now()
    if existing:
        existing.file_url = upload_result["url"]
        existing.file_name = upload_result.get("filename")
        existing.file_size = upload_result.get("size")
        existing.file_type = ext or None
        existing.text_value = None
        existing.status = "approved"
        existing.reviewed_by = None
        existing.reviewed_at = now
        existing.rejection_reason = None
        submission = existing
    else:
        submission = EmployeeDocumentSubmission(
            id=uuid.uuid4(),
            org_id=document_type.org_id,
            user_id=user.id,
            document_type_id=document_type.id,
            file_url=upload_result["url"],
            file_name=upload_result.get("filename"),
            file_size=upload_result.get("size"),
            file_type=ext or None,
            status="approved",
            reviewed_by=None,
            reviewed_at=now,
        )
        db.add(submission)

    await db.flush()
    await _after_submission_change(db, user.id)
    await db.refresh(submission)
    return submission


async def submit_text_value(
    db: AsyncSession, user: User, document_type: EmployeeDocumentType, text_value: str
) -> EmployeeDocumentSubmission:
    """
    ثبت مقدار متنی (فقط input_type=text — مثال: شماره حساب بانکی) —
    تأیید خودکار در همین لحظه، هم‌الگو با submit_document.
    """
    if document_type.input_type != "text":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{document_type.name}» از نوع مقدار متنی نیست — از endpoint آپلود فایل استفاده کنید")
    value = text_value.strip()
    if not value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مقدار نمی‌تواند خالی باشد")

    existing = await get_submission(db, user.id, document_type.id)
    now = _now()
    if existing:
        existing.text_value = value
        existing.file_url = None
        existing.file_name = None
        existing.file_size = None
        existing.file_type = None
        existing.status = "approved"
        existing.reviewed_by = None
        existing.reviewed_at = now
        existing.rejection_reason = None
        submission = existing
    else:
        submission = EmployeeDocumentSubmission(
            id=uuid.uuid4(),
            org_id=document_type.org_id,
            user_id=user.id,
            document_type_id=document_type.id,
            text_value=value,
            status="approved",
            reviewed_by=None,
            reviewed_at=now,
        )
        db.add(submission)

    await db.flush()
    await _after_submission_change(db, user.id)
    await db.refresh(submission)
    return submission


def submission_to_response(submission: EmployeeDocumentSubmission, document_type_name: str) -> DocumentSubmissionResponse:
    return DocumentSubmissionResponse(
        id=str(submission.id),
        document_type_id=str(submission.document_type_id),
        document_type_name=document_type_name,
        file_url=submission.file_url,
        file_name=submission.file_name,
        file_size=submission.file_size,
        file_type=submission.file_type,
        text_value=submission.text_value,
        status=submission.status,
        rejection_reason=submission.rejection_reason,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


# ─── وضعیت کامل کاربر — «مسیر ورود من» + Monitoring + پروفایل کاربر ────────

async def _documents_status_for_user(db: AsyncSession, user: User) -> DocumentsStatus:
    if user.org_id is None:
        return DocumentsStatus(completed=True, required_count=0, submitted_count=0, items=[])

    doc_types = await list_document_types(db, user.org_id, active_only=True)
    submissions_result = await db.execute(
        select(EmployeeDocumentSubmission).where(EmployeeDocumentSubmission.user_id == user.id)
    )
    submissions_map = {s.document_type_id: s for s in submissions_result.scalars().all()}

    items = []
    for dt in doc_types:
        sub = submissions_map.get(dt.id)
        items.append(DocumentTypeStatusResponse(
            document_type_id=str(dt.id),
            document_type_name=dt.name,
            description=dt.description,
            input_type=dt.input_type,
            is_required=dt.is_required,
            allowed_extensions=dt.allowed_extensions or [],
            max_size_mb=dt.max_size_mb,
            template_file_url=dt.template_file_url,
            status=sub.status if sub else "not_uploaded",
            file_url=sub.file_url if sub else None,
            file_name=sub.file_name if sub else None,
            text_value=sub.text_value if sub else None,
            rejection_reason=sub.rejection_reason if sub else None,
            uploaded_at=sub.created_at if sub else None,
        ))

    required_count = sum(1 for d in items if d.is_required)
    submitted_count = sum(1 for d in items if d.status == "approved")
    required_ok = all(d.status == "approved" for d in items if d.is_required)
    return DocumentsStatus(
        completed=required_ok, required_count=required_count, submitted_count=submitted_count, items=items,
    )


async def get_employee_status(db: AsyncSession, user: User) -> EmployeeOnboardingStatusResponse:
    """وضعیت کامل Employee Onboarding یک کاربر — «مسیر ورود من»، Monitoring، و بخش مدارک در پروفایل کاربر."""
    is_blocked = await onboarding_service.get_employee_onboarding_gate_status(db, user.id)

    rows = (await db.execute(
        select(UserProgramEnrollment, OnboardingProgram)
        .join(OnboardingProgram, OnboardingProgram.id == UserProgramEnrollment.program_id)
        .where(UserProgramEnrollment.user_id == user.id, OnboardingProgram.purpose == "employee_onboarding")
        .order_by(UserProgramEnrollment.enrolled_at.desc())
    )).all()

    enrollments: list[EmployeeOnboardingEnrollmentSummary] = []
    last_activity_at = None
    if rows:
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

        for e, p in rows:
            enrollments.append(EmployeeOnboardingEnrollmentSummary(
                enrollment_id=str(e.id),
                program_id=str(p.id),
                program_name=p.name,
                enrolled_at=e.enrolled_at,
                deadline_at=e.deadline_at,
                completed_at=e.completed_at,
                progress_pct=e.progress_pct,
                steps_total=steps_total_map.get(p.id, 0),
                steps_completed=completed_map.get(e.id, 0),
            ))
            if last_activity_at is None or e.updated_at > last_activity_at:
                last_activity_at = e.updated_at

    documents = await _documents_status_for_user(db, user)

    return EmployeeOnboardingStatusResponse(
        user_id=str(user.id),
        user_name=user.full_name,
        user_email=user.email,
        is_blocked=is_blocked,
        last_activity_at=last_activity_at,
        enrollments=enrollments,
        documents=documents,
    )


async def list_employee_statuses(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    blocked_only: bool = False,
) -> tuple[list[EmployeeOnboardingStatusResponse], int]:
    """
    نمای مدیریتی Monitoring — فقط کاربرانی که حداقل یک Enrollment در یک
    Program با purpose=employee_onboarding دارند (یعنی حداقل یک‌بار برایشان
    مسیری انتخاب شده).
    """
    q = (
        select(User)
        .join(UserProgramEnrollment, UserProgramEnrollment.user_id == User.id)
        .join(OnboardingProgram, OnboardingProgram.id == UserProgramEnrollment.program_id)
        .where(User.org_id == org_id, OnboardingProgram.purpose == "employee_onboarding")
        .distinct()
    )
    if search:
        q = q.where(User.full_name.ilike(f"%{search.strip()}%"))

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    users = (await db.execute(q)).scalars().all()
    items = [await get_employee_status(db, u) for u in users]

    if blocked_only:
        # توجه: فیلتر بعد از صفحه‌بندی اعمال می‌شود — با blocked_only، total ممکن است
        # دقیقاً برابر تعداد آیتم‌های بازگشتی نباشد (محدودیت شناخته‌شده در V1).
        items = [i for i in items if i.is_blocked]

    return items, total
