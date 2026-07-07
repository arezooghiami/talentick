"""
Talentick — Content Endpoint Tests
=====================================
پوشش:
- ساخت محتوا: فقط org_admin به بالا مجاز است (employee → 403)
- کارمند فقط محتوای published سازمان خودش را می‌بیند (draft مخفی می‌ماند)
- Org Isolation: کاربر یک سازمان به محتوای سازمان دیگر دسترسی ندارد (404)
- ویرایش/حذف محتوا فقط توسط org_admin
- افزودن آیتم به محتوا و بازگشت آن در جزئیات محتوا
"""
from httpx import AsyncClient

from app.models.organization import Organization
from app.models.user import User


def _content_payload(**overrides) -> dict:
    payload = {
        "title": "دوره آشنایی با سازمان",
        "type": "course",
        "description": "توضیح دوره",
        "status": "draft",
        "tags": ["onboarding"],
    }
    payload.update(overrides)
    return payload


async def test_employee_cannot_create_content(client: AsyncClient, employee_headers: dict):
    res = await client.post("/api/contents/", json=_content_payload(), headers=employee_headers)
    assert res.status_code == 403


async def test_org_admin_can_create_content(client: AsyncClient, org_admin_headers: dict):
    res = await client.post("/api/contents/", json=_content_payload(), headers=org_admin_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "دوره آشنایی با سازمان"
    assert body["status"] == "draft"
    assert body["items"] == []


async def test_invalid_content_type_rejected(client: AsyncClient, org_admin_headers: dict):
    res = await client.post(
        "/api/contents/", json=_content_payload(type="not-a-real-type"), headers=org_admin_headers
    )
    assert res.status_code == 400


async def test_employee_only_sees_published_content(client: AsyncClient, org_admin_headers: dict, employee_headers: dict):
    # یک محتوای draft و یک محتوای published می‌سازیم
    await client.post("/api/contents/", json=_content_payload(title="پیش‌نویس", status="draft"), headers=org_admin_headers)
    await client.post("/api/contents/", json=_content_payload(title="منتشرشده", status="published"), headers=org_admin_headers)

    # org_admin هر دو را می‌بیند
    res_admin = await client.get("/api/contents/", headers=org_admin_headers)
    assert res_admin.status_code == 200
    assert res_admin.json()["total"] == 2

    # employee فقط published را می‌بیند
    res_employee = await client.get("/api/contents/", headers=employee_headers)
    assert res_employee.status_code == 200
    body = res_employee.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "منتشرشده"


async def test_employee_gets_404_for_draft_content_detail(client: AsyncClient, org_admin_headers: dict, employee_headers: dict):
    create_res = await client.post("/api/contents/", json=_content_payload(status="draft"), headers=org_admin_headers)
    content_id = create_res.json()["id"]

    res = await client.get(f"/api/contents/{content_id}", headers=employee_headers)
    assert res.status_code == 404


async def test_org_isolation_on_content(
    client: AsyncClient,
    org_admin_headers: dict,
    other_org: Organization,
    db_session,
):
    """کاربر سازمان دیگر نباید به محتوای این سازمان دسترسی داشته باشد."""
    from app.core.security import hash_password
    import uuid

    create_res = await client.post("/api/contents/", json=_content_payload(status="published"), headers=org_admin_headers)
    content_id = create_res.json()["id"]

    other_admin = User(
        id=uuid.uuid4(),
        org_id=other_org.id,
        email="admin@other-org.local",
        full_name="ادمین سازمان دیگر",
        hashed_password=hash_password("Password@123"),
        role="org_admin",
        is_active=True,
    )
    db_session.add(other_admin)
    await db_session.commit()

    login_res = await client.post(
        "/api/auth/login", data={"username": other_admin.email, "password": "Password@123"}
    )
    other_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res = await client.get(f"/api/contents/{content_id}", headers=other_headers)
    assert res.status_code == 403


async def test_update_and_delete_content(client: AsyncClient, org_admin_headers: dict):
    create_res = await client.post("/api/contents/", json=_content_payload(), headers=org_admin_headers)
    content_id = create_res.json()["id"]

    update_res = await client.patch(
        f"/api/contents/{content_id}", json={"status": "published"}, headers=org_admin_headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "published"

    delete_res = await client.delete(f"/api/contents/{content_id}", headers=org_admin_headers)
    assert delete_res.status_code == 204

    get_res = await client.get(f"/api/contents/{content_id}", headers=org_admin_headers)
    assert get_res.status_code == 404


async def test_add_item_to_content(client: AsyncClient, org_admin_headers: dict):
    create_res = await client.post("/api/contents/", json=_content_payload(), headers=org_admin_headers)
    content_id = create_res.json()["id"]

    item_res = await client.post(
        f"/api/contents/{content_id}/items",
        json={"title": "معرفی سازمان", "type": "video", "media_url": "https://example.com/v.mp4"},
        headers=org_admin_headers,
    )
    assert item_res.status_code == 201
    assert item_res.json()["title"] == "معرفی سازمان"

    detail_res = await client.get(f"/api/contents/{content_id}", headers=org_admin_headers)
    detail = detail_res.json()
    assert detail["total_items_count"] == 1
    assert len(detail["items"]) == 1
