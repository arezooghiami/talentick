"""
Talentick — Onboarding Router (Admin)
=========================================
برنامه‌ی آشنایی سازمانی (Learning Journey) — چندمرحله‌ای، با هدف‌گذاری
نقش/واحد و امکان ثبت‌نام خودکار کارکنان جدید (is_default).

Routes:
  GET    /api/onboarding/programs                       → لیست برنامه‌ها (مدیریتی)
  POST   /api/onboarding/programs                       → ساخت برنامه‌ی جدید
  GET    /api/onboarding/programs/{id}                   → جزئیات + مراحل
  PATCH  /api/onboarding/programs/{id}                   → ویرایش
  DELETE /api/onboarding/programs/{id}                   → حذف
  POST   /api/onboarding/programs/{id}/steps             → افزودن مرحله
  PATCH  /api/onboarding/steps/{step_id}                 → ویرایش مرحله
  DELETE /api/onboarding/steps/{step_id}                 → حذف مرحله
  GET    /api/onboarding/programs/{id}/enrollments        → پیگیری پیشرفت کارکنان ثبت‌نام‌شده
  POST   /api/onboarding/programs/{id}/enroll             → ثبت‌نام دستی کاربران مشخص

مشاهده/تکمیل مسیر آنبوردینگ خودم برای کارمند از routers/me.py
(GET /api/me/onboarding و ...) است.

دسترسی: مدیریت (ساخت/ویرایش/حذف/ثبت‌نام) فقط org_admin به بالا —
هم‌راستا با content.py/announcements.py.

super_admin: مثل content.py می‌تواند org_id بدهد (لیست یک سازمان خاص) یا
ندهد (لیست همه‌ی سازمان‌ها) — برای ساخت همیشه یک org_id مشخص لازم است.
"""

from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import OrgAdmin
from app.dependencies import enforce_org_scope as _enforce_org_scope
from app.models.user import User
from app.schemas.onboarding import (
    EnrollmentListResponse,
    EnrollRequest,
    OnboardingProgramCreate,
    OnboardingProgramDetailResponse,
    OnboardingProgramListResponse,
    OnboardingProgramUpdate,
    ProgramStepCreate,
    ProgramStepResponse,
    ProgramStepUpdate,
)
from app.services import onboarding_service

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


def _resolve_org_id(current_user: User, org_id: str | None) -> uuid.UUID | None:
    """هم‌راستا با content._resolve_org_id / announcements._resolve_org_id."""
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


def _resolve_required_org_id(current_user: User, org_id: str | None) -> uuid.UUID:
    resolved = _resolve_org_id(current_user, org_id)
    if resolved is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "org_id الزامی است")
    return resolved


async def _get_program_or_404(db: AsyncSession, program_id: str):
    program = await onboarding_service.get_program(db, program_id)
    if not program:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "برنامه یافت نشد")
    return program


async def _get_step_or_404(db: AsyncSession, step_id: str):
    step = await onboarding_service.get_step(db, step_id)
    if not step:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مرحله یافت نشد")
    return step


# ─── Programs ─────────────────────────────────────────────────────────────

@router.get("/programs", response_model=OnboardingProgramListResponse, summary="لیست برنامه‌های آشنایی (مدیریتی)")
async def list_programs(
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    org_id: str | None = Query(None, description="فقط super_admin — خالی = همه سازمان‌ها"),
):
    target_org_id = _resolve_org_id(current_user, org_id)
    items, total = await onboarding_service.list_programs(
        db, target_org_id, page=page, page_size=page_size, search=search,
    )
    responses = [await onboarding_service.program_to_response(db, p) for p in items]
    return OnboardingProgramListResponse(
        items=responses, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/programs", response_model=OnboardingProgramDetailResponse, status_code=status.HTTP_201_CREATED,
    summary="ساخت برنامه‌ی آشنایی جدید",
)
async def create_program(
    body: OnboardingProgramCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    org_id = _resolve_required_org_id(current_user, body.org_id)
    program = await onboarding_service.create_program(db, org_id, current_user.id, body)
    return await onboarding_service.program_to_detail(db, program)


@router.get("/programs/{program_id}", response_model=OnboardingProgramDetailResponse, summary="جزئیات برنامه + مراحل")
async def get_program(
    program_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    program = await _get_program_or_404(db, program_id)
    _enforce_org_scope(current_user, program.org_id)
    return await onboarding_service.program_to_detail(db, program)


@router.patch("/programs/{program_id}", response_model=OnboardingProgramDetailResponse, summary="ویرایش برنامه")
async def update_program(
    program_id: str,
    body: OnboardingProgramUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    program = await _get_program_or_404(db, program_id)
    _enforce_org_scope(current_user, program.org_id)
    updated = await onboarding_service.update_program(db, program, body)
    return await onboarding_service.program_to_detail(db, updated)


@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف برنامه")
async def delete_program(
    program_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    program = await _get_program_or_404(db, program_id)
    _enforce_org_scope(current_user, program.org_id)
    await onboarding_service.delete_program(db, program)


# ─── Steps ────────────────────────────────────────────────────────────────

@router.post(
    "/programs/{program_id}/steps", response_model=ProgramStepResponse, status_code=status.HTTP_201_CREATED,
    summary="افزودن مرحله به برنامه",
)
async def add_step(
    program_id: str,
    body: ProgramStepCreate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    program = await _get_program_or_404(db, program_id)
    _enforce_org_scope(current_user, program.org_id)
    step = await onboarding_service.add_step(db, program, body)
    return await onboarding_service.step_to_response(db, step)


@router.patch("/steps/{step_id}", response_model=ProgramStepResponse, summary="ویرایش مرحله")
async def update_step(
    step_id: str,
    body: ProgramStepUpdate,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    step = await _get_step_or_404(db, step_id)
    _enforce_org_scope(current_user, step.org_id)
    updated = await onboarding_service.update_step(db, step, body)
    return await onboarding_service.step_to_response(db, updated)


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT, summary="حذف مرحله")
async def delete_step(
    step_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    step = await _get_step_or_404(db, step_id)
    _enforce_org_scope(current_user, step.org_id)
    await onboarding_service.delete_step(db, step)


# ─── Enrollments (پیگیری پیشرفت کارکنان) ───────────────────────────────────

@router.get(
    "/programs/{program_id}/enrollments", response_model=EnrollmentListResponse,
    summary="پیگیری پیشرفت کارکنان ثبت‌نام‌شده در این برنامه",
)
async def list_enrollments(
    program_id: str,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    program = await _get_program_or_404(db, program_id)
    _enforce_org_scope(current_user, program.org_id)
    items, total = await onboarding_service.list_enrollments(db, program, page=page, page_size=page_size)
    return EnrollmentListResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/programs/{program_id}/enroll", response_model=EnrollmentListResponse,
    summary="ثبت‌نام دستی کاربران مشخص در این برنامه",
    description="برای برنامه‌هایی که is_default نیستند (یا برای ثبت‌نام مجدد یک کاربر خاص) — کاربران باید در همان سازمان برنامه باشند.",
)
async def enroll_users(
    program_id: str,
    body: EnrollRequest,
    current_user: OrgAdmin,
    db: AsyncSession = Depends(get_db),
):
    program = await _get_program_or_404(db, program_id)
    _enforce_org_scope(current_user, program.org_id)

    for raw_id in body.user_ids:
        try:
            user_uuid = uuid.UUID(raw_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"شناسه کاربر نامعتبر: {raw_id}")
        user = await db.get(User, user_uuid)
        if not user or str(user.org_id) != str(program.org_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کاربر یافت نشد یا متعلق به این سازمان نیست: {raw_id}")
        await onboarding_service.enroll_user(db, program, user, enrolled_by=current_user.id)

    items, total = await onboarding_service.list_enrollments(db, program, page=1, page_size=100)
    return EnrollmentListResponse(items=items, total=total, page=1, page_size=100, total_pages=1)
