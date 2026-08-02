"""
Talentick — Employee Onboarding Endpoint Tests
==================================================
پوشش (بعد از بازطراحی مشترک با ماژول آنبوردینگ):
- «مسیر ورود کارمند جدید» خودش یک OnboardingProgram با
  purpose=employee_onboarding است — با purpose=learning (پیش‌فرض) مخلوط نمی‌شود.
- کاتالوگ مدارک (Document Types): CRUD + اعتبارسنجی input_type (file/text)
- نوع مرحله‌ی document_upload خودکار محاسبه می‌شود، دستی تکمیل‌شدنی نیست.
- Gate کامل: کاربری که به یک مسیر Employee Onboarding Enroll شده، تا
  تکمیل همه‌ی مراحل اجباری (شامل مرحله‌ی خودکار مدارک) مسدود است.
- کاربر General (org_id=None) نمی‌تواند به مسیر Employee Onboarding
  اختصاص داده شود.

نکته: این تست‌ها به PostgreSQL واقعی نیاز دارند (conftest.py) — در محیط
فعلی (بدون deps نصب‌شده) اجرا نشده‌اند؛ قبل از merge با `pytest` واقعی
تأیید شوند.
"""
from __future__ import annotations

from httpx import AsyncClient

from app.models.organization import Organization


def _doctype_payload(**overrides) -> dict:
    payload = {
        "name": "کپی کارت ملی",
        "input_type": "file",
        "is_required": True,
        "allowed_extensions": ["pdf", "jpg"],
        "order_index": 0,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# ─── تفکیک purpose ───────────────────────────────────────────────────────

async def test_program_default_purpose_is_learning(client: AsyncClient, org_admin_headers: dict):
    res = await client.post(
        "/api/onboarding/programs", json={"name": "دوره‌ی معمولی"}, headers=org_admin_headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["purpose"] == "learning"


async def test_learning_and_employee_onboarding_lists_are_isolated(client: AsyncClient, org_admin_headers: dict):
    await client.post("/api/onboarding/programs", json={"name": "دوره یادگیری"}, headers=org_admin_headers)
    await client.post(
        "/api/onboarding/programs",
        json={"name": "ورود کارمند جدید", "purpose": "employee_onboarding"},
        headers=org_admin_headers,
    )

    learning_res = await client.get("/api/onboarding/programs?purpose=learning", headers=org_admin_headers)
    eo_res = await client.get("/api/onboarding/programs?purpose=employee_onboarding", headers=org_admin_headers)

    assert learning_res.json()["total"] == 1
    assert learning_res.json()["items"][0]["name"] == "دوره یادگیری"
    assert eo_res.json()["total"] == 1
    assert eo_res.json()["items"][0]["name"] == "ورود کارمند جدید"


async def test_employee_onboarding_program_cannot_be_public(client: AsyncClient, super_admin_headers: dict):
    res = await client.post(
        "/api/onboarding/programs",
        json={"name": "ورود عمومی", "purpose": "employee_onboarding", "is_public": True},
        headers=super_admin_headers,
    )
    assert res.status_code == 400


# ─── Document Types ─────────────────────────────────────────────────────

async def test_create_text_document_type(client: AsyncClient, org_admin_headers: dict):
    res = await client.post(
        "/api/employee-onboarding/document-types",
        json=_doctype_payload(name="شماره حساب بانک سینا", input_type="text", allowed_extensions=[]),
        headers=org_admin_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["input_type"] == "text"
    assert body["allowed_extensions"] == []


async def test_invalid_input_type_rejected(client: AsyncClient, org_admin_headers: dict):
    res = await client.post(
        "/api/employee-onboarding/document-types",
        json=_doctype_payload(input_type="video"),
        headers=org_admin_headers,
    )
    assert res.status_code == 400


async def test_employee_cannot_manage_document_types(client: AsyncClient, employee_headers: dict):
    res = await client.get("/api/employee-onboarding/document-types", headers=employee_headers)
    assert res.status_code == 403


# ─── مرحله‌ی document_upload — خودکار، نه دستی ──────────────────────────

async def test_document_upload_step_cannot_be_completed_manually(
    client: AsyncClient, org_admin_headers: dict, org: Organization,
):
    prog_res = await client.post(
        "/api/onboarding/programs",
        json={"name": "ورود کارمند", "purpose": "employee_onboarding"},
        headers=org_admin_headers,
    )
    program_id = prog_res.json()["id"]
    step_res = await client.post(
        f"/api/onboarding/programs/{program_id}/steps",
        json={"title": "آپلود مدارک", "type": "document_upload", "is_required": True, "order_index": 0},
        headers=org_admin_headers,
    )
    step_id = step_res.json()["id"]

    new_user_res = await client.post(
        "/api/users/",
        json={
            "phone": "09120000097", "full_name": "کارمند تست", "role": "employee",
            "org_id": str(org.id), "password": "Password@123",
            "employee_onboarding_program_id": program_id,
        },
        headers=org_admin_headers,
    )
    assert new_user_res.status_code == 201, new_user_res.text

    login_res = await client.post("/api/auth/login", data={"username": "09120000097", "password": "Password@123"})
    change_res = await client.post(
        "/api/auth/change-password",
        json={"current_password": "Password@123", "new_password": "NewPassword@123"},
        headers={"Authorization": f"Bearer {login_res.json()['access_token']}"},
    )
    new_headers = {"Authorization": f"Bearer {change_res.json()['access_token']}"}

    complete_res = await client.post(
        f"/api/me/onboarding/steps/{step_id}/complete", json={}, headers=new_headers
    )
    assert complete_res.status_code == 400


# ─── کاربر General نمی‌تواند به مسیر Employee Onboarding اختصاص یابد ────

async def test_general_user_cannot_be_assigned_employee_onboarding_program(
    client: AsyncClient, super_admin_headers: dict, org: Organization,
):
    prog_res = await client.post(
        "/api/onboarding/programs",
        json={"name": "ورود کارمند", "purpose": "employee_onboarding", "org_id": str(org.id)},
        headers=super_admin_headers,
    )
    program_id = prog_res.json()["id"]

    res = await client.post(
        "/api/users/",
        json={
            "phone": "09120000096", "full_name": "کاربر عمومی", "role": "employee",
            "org_id": None, "password": "Password@123",
            "employee_onboarding_program_id": program_id,
        },
        headers=super_admin_headers,
    )
    assert res.status_code == 400


# ─── Gate کامل — سناریوی سرتاسری ────────────────────────────────────────

async def test_full_gate_flow_blocks_then_unblocks(
    client: AsyncClient, org_admin_headers: dict, org: Organization,
):
    """
    سناریو: مسیر Employee Onboarding با دو مرحله‌ی اجباری می‌سازیم —
    یکی custom (خوش‌آمدگویی) و یکی document_upload (خودکار از کاتالوگ).
    کاربر جدید مستقیماً هنگام ساخت به این مسیر Enroll می‌شود (دراپ‌داون
    فرم کاربر) → باید مسدود باشد → بعد از تکمیل هر دو مرحله → آزاد می‌شود.
    """
    prog_res = await client.post(
        "/api/onboarding/programs",
        json={"name": "ورود کارمند جدید", "purpose": "employee_onboarding"},
        headers=org_admin_headers,
    )
    assert prog_res.status_code == 201, prog_res.text
    program_id = prog_res.json()["id"]

    welcome_step_res = await client.post(
        f"/api/onboarding/programs/{program_id}/steps",
        json={"title": "خوش‌آمدگویی", "type": "custom", "is_required": True, "order_index": 0},
        headers=org_admin_headers,
    )
    assert welcome_step_res.status_code == 201, welcome_step_res.text
    welcome_step_id = welcome_step_res.json()["id"]

    doc_step_res = await client.post(
        f"/api/onboarding/programs/{program_id}/steps",
        json={"title": "آپلود مدارک", "type": "document_upload", "is_required": True, "order_index": 1},
        headers=org_admin_headers,
    )
    assert doc_step_res.status_code == 201, doc_step_res.text

    dt_res = await client.post(
        "/api/employee-onboarding/document-types",
        json=_doctype_payload(name="شماره حساب بانک سینا", input_type="text", allowed_extensions=[]),
        headers=org_admin_headers,
    )
    assert dt_res.status_code == 201, dt_res.text
    dt_id = dt_res.json()["id"]

    create_res = await client.post(
        "/api/users/",
        json={
            "phone": "09120000095", "full_name": "کارمند جدید", "role": "employee",
            "org_id": str(org.id), "password": "Password@123",
            "employee_onboarding_program_id": program_id,
        },
        headers=org_admin_headers,
    )
    assert create_res.status_code == 201, create_res.text
    new_user_id = create_res.json()["id"]

    login_res = await client.post(
        "/api/auth/login", data={"username": "09120000095", "password": "Password@123"}
    )
    assert login_res.status_code == 200, login_res.text
    change_res = await client.post(
        "/api/auth/change-password",
        json={"current_password": "Password@123", "new_password": "NewPassword@123"},
        headers={"Authorization": f"Bearer {login_res.json()['access_token']}"},
    )
    assert change_res.status_code == 200, change_res.text
    new_headers = {"Authorization": f"Bearer {change_res.json()['access_token']}"}

    # هنوز هیچ مرحله‌ای تکمیل نشده — باید مسدود باشد
    blocked_res = await client.get("/api/me/contents", headers=new_headers)
    assert blocked_res.status_code == 403
    assert blocked_res.json()["detail"]["code"] == "employee_onboarding_required"

    # مسیر خودِ Employee Onboarding معاف است
    status_res = await client.get("/api/employee-onboarding/me/status", headers=new_headers)
    assert status_res.status_code == 200, status_res.text
    enrollment_id = status_res.json()["enrollments"][0]["enrollment_id"]

    # تکمیل مرحله‌ی خوش‌آمدگویی
    complete_res = await client.post(
        f"/api/me/onboarding/steps/{welcome_step_id}/complete", json={}, headers=new_headers
    )
    assert complete_res.status_code == 200, complete_res.text

    # هنوز مدارک باقی مانده — همچنان مسدود
    still_blocked = await client.get("/api/me/contents", headers=new_headers)
    assert still_blocked.status_code == 403

    # ثبت مدرک متنی
    submit_res = await client.post(
        f"/api/employee-onboarding/me/document-types/{dt_id}/submit-text",
        json={"text_value": "IR000000000000000000000002"},
        headers=new_headers,
    )
    assert submit_res.status_code == 200, submit_res.text

    # هر دو مرحله تکمیل شد — باید آزاد باشد
    unblocked_res = await client.get("/api/me/contents", headers=new_headers)
    assert unblocked_res.status_code == 200, unblocked_res.text

    # جزئیات enrollment باید completed_at داشته باشد
    detail_res = await client.get(f"/api/me/onboarding/{enrollment_id}", headers=new_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["completed_at"] is not None

    # Monitoring باید is_blocked=False نشان دهد
    mon_res = await client.get(
        f"/api/employee-onboarding/monitoring?org_id={org.id}", headers=org_admin_headers,
    )
    assert mon_res.status_code == 200, mon_res.text
    mon_item = next(i for i in mon_res.json()["items"] if i["user_id"] == new_user_id)
    assert mon_item["is_blocked"] is False
    assert mon_item["documents"]["completed"] is True

    # نمای مدیریتی کامل (بخش «مدارک» در پروفایل کاربر)
    detail_mon_res = await client.get(
        f"/api/employee-onboarding/monitoring/{new_user_id}", headers=org_admin_headers,
    )
    assert detail_mon_res.status_code == 200, detail_mon_res.text
    doc_item = detail_mon_res.json()["documents"]["items"][0]
    assert doc_item["text_value"] == "IR000000000000000000000002"
    assert doc_item["status"] == "approved"
