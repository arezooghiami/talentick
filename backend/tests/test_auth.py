"""
Talentick — Auth Endpoint Tests
=================================
پوشش:
- ورود موفق و ساخت access token معتبر
- ورود با پسورد اشتباه → 401
- ورود با ایمیل ناموجود → 401
- ورود کاربر غیرفعال (Soft-Deleted) → 401
- GET /api/auth/me با/بدون توکن معتبر
"""
from httpx import AsyncClient

from app.models.user import User


async def test_login_success(client: AsyncClient, org_admin_user: User):
    res = await client.post(
        "/api/auth/login",
        data={"username": org_admin_user.email, "password": "Password@123"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["role"] == "org_admin"
    assert body["user_id"] == str(org_admin_user.id)


async def test_login_wrong_password(client: AsyncClient, org_admin_user: User):
    res = await client.post(
        "/api/auth/login",
        data={"username": org_admin_user.email, "password": "wrong-password"},
    )
    assert res.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    res = await client.post(
        "/api/auth/login",
        data={"username": "no-such-user@test.local", "password": "whatever"},
    )
    assert res.status_code == 401


async def test_login_inactive_user_rejected(client: AsyncClient, employee_user: User, db_session):
    """کاربر Soft-Delete شده (is_active=False) نباید بتواند لاگین کند."""
    employee_user.is_active = False
    db_session.add(employee_user)
    await db_session.commit()

    res = await client.post(
        "/api/auth/login",
        data={"username": employee_user.email, "password": "Password@123"},
    )
    assert res.status_code == 401


async def test_me_requires_token(client: AsyncClient):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, org_admin_user: User, org_admin_headers: dict):
    res = await client.get("/api/auth/me", headers=org_admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == str(org_admin_user.id)
    assert body["email"] == org_admin_user.email
    assert body["role"] == "org_admin"
    assert body["is_active"] is True


async def test_me_rejects_invalid_token(client: AsyncClient):
    res = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401
