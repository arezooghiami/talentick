"""
Talentick — Employee Onboarding Router (کاتالوگ مدارک + Monitoring)
========================================================================
«مسیر ورود کارمند جدید» خودش دیگر یک Config جداگانه نیست — یک
app.models.onboarding.OnboardingProgram با purpose="employee_onboarding"
است. ساخت/ویرایش مسیر و مراحلش (شامل نوع document_upload) از همان
API موجود ماژول آنبوردینگ انجام می‌شود:

    POST/PATCH/GET  /api/onboarding/programs?purpose=employee_onboarding
    POST/PATCH/GET  /api/onboarding/programs/{id}/steps , /steps/{id}

این روتر فقط مسئول دو چیز مستقل است که آن ماژول ندارد:

Routes (مدیریتی — فقط SuperAdmin/OrgAdmin):
  GET    /api/employee-onboarding/document-types                  → کاتالوگ مدارک سازمان
  POST   /api/employee-onboarding/document-types                  → افزودن قلم جدید
  GET    /api/employee-onboarding/document-types/{id}             → جزئیات یک قلم
  PATCH  /api/employee-onboarding/document-types/{id}             → ویرایش
  DELETE /api/employee-onboarding/document-types/{id}             → حذف (اگر سابقه دارد → 400)
  POST   /api/employee-onboarding/document-types/upload-template  → آپلود فرم خام
  GET    /api/employee-onboarding/monitoring                      → وضعیت همه‌ی کارکنانِ ثبت‌نام‌شده در مسیرهای Employee Onboarding
  GET    /api/employee-onboarding/monitoring/{user_id}             → وضعیت کامل یک کارمند (همچنین برای بخش «مدارک» در پروفایل کاربر)

Routes («مسیر ورود من» — هر کاربر فعال؛ این مسیرها در Gate
dependencies.py معاف‌اند):
  GET    /api/employee-onboarding/me/status                                        → وضعیت کامل من (مسیرها + مدارک)
  POST   /api/employee-onboarding/me/document-types/{id}/upload-file               → آپلود فایل (input_type=file)
  POST   /api/employee-onboarding/me/document-types/{id}/submit-text               → ثبت مقدار متنی (input_type=text)

مشاهده/تکمیل خودِ مراحل محتوا/آزمون مسیر Employee Onboarding کارمند از
همان routers/me.py (GET /api/me/onboarding و ...) است — چون همان موتور
مشترک است، اندپوینت جداگانه‌ای لازم نیست.

نکته برای فرانت: خطای Gate (وقتی کاربر مسدود است) روی *هر* endpoint دیگر
سیستم به‌صورت 403 با بدنه‌ی `{"code": "employee_onboarding_required"}`
برمی‌گردد (dependencies.get_current_user).
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import upload_file
from app.database import get_db
from app.dependencies import Employee, OrgAdmin
from app.dependencies import enforce_org_scope as _enforce_org_scope
from app.models.user import User
from app.schemas.content import UploadResponse
from app.schemas.employee_onboarding import (
    DocumentSubmissionResponse,
    EmployeeDocumentTypeCreate,
    EmployeeDocumentTypeResponse,
    EmployeeDocumentTypeUpdate,
    EmployeeOnboardingStatusListResponse,
    EmployeeOnboardingStatusResponse,
    TextValueSubmitRequest,
)
from app.services import employee_onboarding_service

router = APIRouter(prefix="/api/employee-onboarding", tags=["Employee Onboarding"])


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID:
    """هم‌راستا با documents._resolve_org_id/onboarding._resolve_required_org_id."""
    if current_user.role == "super_admin" and org_id:
        try:
            return uuid.UUID(org_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id نامعتبر است")
    if current_user.org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return current_user.org_id


# ═══════════════════════════════════════════════════════════════════════════
# کاتالوگ مدارک (Document Types) — فقط SuperAdmin/OrgAdmin
# ═══════════════════════════════════════════════════════════════════════════

async def _get_document_type_or_404(db: AsyncSession, document_type_id: str):
    doc_type = await employee_onboarding_service.get_document_type(db, document_type_id)
    if not doc_type:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قلم موردنظر یافت نشد")
    return doc_type


@router.get("/document-types", response_model=list[EmployeeDocumentTypeResponse], summary="کاتالوگ مدارک موردنیاز سازمان")
async def list_document_types(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = سازمان خودش"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    doc_types = await employee_onboarding_service.list_document_types(db, target_org_id)
    return [await employee_onboarding_service.document_type_to_response(db, d) for d in doc_types]


@router.post(
    "/document-types", response_model=EmployeeDocumentTypeResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن قلم جدید به کاتالوگ مدارک",
)
async def create_document_type(
    body: EmployeeDocumentTypeCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    org_id = _resolve_org_id(current_user, body.org_id)
    doc_type = await employee_onboarding_service.create_document_type(db, org_id, body)
    return await employee_onboarding_service.document_type_to_response(db, doc_type)


@router.post(
    "/document-types/upload-template", response_model=UploadResponse,
    summary="آپلود فرم خام (برای template_file_url — مثال: فرم افتتاح حساب بانکی)",
)
async def upload_document_type_template(
    current_user: OrgAdmin,
    file: UploadFile = File(...),
    org_id: str | None = Query(None, description="فقط super_admin"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    result = await upload_file(file, target_org_id, subfolder="employee-onboarding-templates")
    return UploadResponse(**result)


@router.get("/document-types/{document_type_id}", response_model=EmployeeDocumentTypeResponse, summary="جزئیات یک قلم")
async def get_document_type(
    document_type_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    doc_type = await _get_document_type_or_404(db, document_type_id)
    _enforce_org_scope(current_user, doc_type.org_id)
    return await employee_onboarding_service.document_type_to_response(db, doc_type)


@router.patch("/document-types/{document_type_id}", response_model=EmployeeDocumentTypeResponse, summary="ویرایش قلم")
async def update_document_type(
    document_type_id: str,
    body: EmployeeDocumentTypeUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    doc_type = await _get_document_type_or_404(db, document_type_id)
    _enforce_org_scope(current_user, doc_type.org_id)
    updated = await employee_onboarding_service.update_document_type(db, doc_type, body)
    return await employee_onboarding_service.document_type_to_response(db, updated)


@router.delete(
    "/document-types/{document_type_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف قلم",
    description="اگر قبلاً توسط کارکنان ثبت شده باشد، حذف رد می‌شود (400) — به‌جایش غیرفعال (is_active=false) کنید.",
)
async def delete_document_type(
    document_type_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    doc_type = await _get_document_type_or_404(db, document_type_id)
    _enforce_org_scope(current_user, doc_type.org_id)
    await employee_onboarding_service.delete_document_type(db, doc_type)


# ═══════════════════════════════════════════════════════════════════════════
# Monitoring + بخش «مدارک» در پروفایل کاربر — فقط SuperAdmin/OrgAdmin
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/monitoring", response_model=EmployeeOnboardingStatusListResponse,
    summary="وضعیت Employee Onboarding همه‌ی کارکنانی که در یک مسیر ثبت‌نام شده‌اند",
)
async def list_monitoring(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    blocked_only: bool = Query(False, description="فقط کارکنانی که هنوز مسدودند"),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = سازمان خودش"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    items, total = await employee_onboarding_service.list_employee_statuses(
        db, target_org_id, page=page, page_size=page_size, search=search, blocked_only=blocked_only,
    )
    return EmployeeOnboardingStatusListResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get(
    "/monitoring/{user_id}", response_model=EmployeeOnboardingStatusResponse,
    summary="وضعیت کامل Employee Onboarding یک کارمند مشخص",
    description="همچنین برای بخش «مدارک Employee Onboarding» در صفحه‌ی جزئیات کاربر (پنل «کاربران») استفاده می‌شود.",
)
async def get_monitoring_detail(
    user_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسه کاربر نامعتبر است")
    target_user = await db.get(User, uid)
    if not target_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربر یافت نشد")
    _enforce_org_scope(current_user, target_user.org_id)
    return await employee_onboarding_service.get_employee_status(db, target_user)


# ═══════════════════════════════════════════════════════════════════════════
# «مسیر ورود من» — هر کاربر فعال (این مسیرها در Gate معاف‌اند)
# ═══════════════════════════════════════════════════════════════════════════

@router.get(
    "/me/status", response_model=EmployeeOnboardingStatusResponse,
    summary="وضعیت کامل فرآیند ورود من",
    description="شامل مسیر(های) Employee Onboarding که در آن‌ها ثبت‌نام شده‌ام (با enrollment_id برای اتصال به /api/me/onboarding/{enrollment_id}) و چک‌لیست کامل مدارک با وضعیت هرکدام.",
)
async def get_my_status(
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    return await employee_onboarding_service.get_employee_status(db, current_user)


async def _get_my_document_type_or_404(db: AsyncSession, current_user: User, document_type_id: str):
    doc_type = await employee_onboarding_service.get_document_type(db, document_type_id)
    if not doc_type or str(doc_type.org_id) != str(current_user.org_id) or not doc_type.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قلم موردنظر یافت نشد")
    return doc_type


@router.post(
    "/me/document-types/{document_type_id}/upload-file", response_model=DocumentSubmissionResponse,
    summary="آپلود مدرک من (فقط input_type=file)",
    description="تأیید خودکار در همان لحظه — نیازی به تأیید دستی ادمین نیست.",
)
async def upload_my_document(
    document_type_id: str,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
):
    doc_type = await _get_my_document_type_or_404(db, current_user, document_type_id)
    if doc_type.input_type != "file":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{doc_type.name}» از نوع آپلود فایل نیست")
    upload_result = await upload_file(file, doc_type.org_id, subfolder="employee-documents")
    submission = await employee_onboarding_service.submit_document(db, current_user, doc_type, upload_result)
    return employee_onboarding_service.submission_to_response(submission, doc_type.name)


@router.post(
    "/me/document-types/{document_type_id}/submit-text", response_model=DocumentSubmissionResponse,
    summary="ثبت مقدار متنی من (فقط input_type=text — مثال: شماره حساب بانکی)",
    description="تأیید خودکار در همان لحظه — نیازی به تأیید دستی ادمین نیست.",
)
async def submit_my_text_value(
    document_type_id: str,
    body: TextValueSubmitRequest,
    current_user: Employee,
    db: AsyncSession = Depends(get_db),
):
    doc_type = await _get_my_document_type_or_404(db, current_user, document_type_id)
    if doc_type.input_type != "text":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{doc_type.name}» از نوع مقدار متنی نیست")
    submission = await employee_onboarding_service.submit_text_value(db, current_user, doc_type, body.text_value)
    return employee_onboarding_service.submission_to_response(submission, doc_type.name)
