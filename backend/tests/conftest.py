"""
Talentick — Pytest Fixtures
=============================
زیرساخت مشترک تست‌ها: دیتابیس تست، AsyncClient، و کاربران seed شده.

نکات مهم:
- این تست‌ها به یک PostgreSQL واقعی نیاز دارند (نه SQLite) چون مدل‌ها از
  انواع اختصاصی Postgres استفاده می‌کنند: UUID، JSONB، ARRAY.
- به‌صورت پیش‌فرض از همان DATABASE_URL تنظیم‌شده در .env استفاده می‌شود اما
  نام دیتابیس با پسوند «_test» جایگزین می‌شود تا داده‌ی توسعه دست‌نخورده
  بماند. برای override دستی:

      TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/talentick_test pytest

  دیتابیس تست باید از قبل در PostgreSQL ساخته شده باشد:

      createdb talentick_test

راه‌اندازی و اجرا:
    docker compose up -d db          # فقط سرویس دیتابیس کافی است
    createdb -h localhost -U talentick talentick_test
    cd backend && pytest
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User


def _test_database_url() -> str:
    """DATABASE_URL دیتابیس تست را می‌سازد — با override از طریق env در صورت وجود."""
    override = os.getenv("TEST_DATABASE_URL")
    if override:
        return override

    from app.config import settings

    base_url = settings.database_url
    # .../talentick → .../talentick_test
    if base_url.rsplit("/", 1)[-1].endswith("_test"):
        return base_url
    return base_url.rsplit("/", 1)[0] + "/talentick_test"


TEST_DATABASE_URL = _test_database_url()

engine_test = create_async_engine(TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(bind=engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_schema():
    """قبل از کل سشن تست: جداول را می‌سازد. بعد از سشن: پاک می‌کند."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine_test.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    یک session تست به ازای هر تست — در انتهای هر تست همه‌ی جداول truncate
    می‌شوند تا تست‌ها از هم مستقل بمانند (به‌جای rollback تراکنش، چون
    router ها خودشان commit صریح می‌زنند).
    """
    async with TestSessionLocal() as session:
        yield session
        await session.close()

    async with engine_test.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient که به همان db_session تست وصل است (override وابستگی get_db)."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def org(db_session: AsyncSession) -> Organization:
    """یک سازمان تستی."""
    organization = Organization(
        id=uuid.uuid4(),
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
        name="سازمان تست",
        settings={},
        plan="pilot",
        is_active=True,
    )
    db_session.add(organization)
    await db_session.commit()
    await db_session.refresh(organization)
    return organization


@pytest_asyncio.fixture
async def other_org(db_session: AsyncSession) -> Organization:
    """یک سازمان دوم — برای تست Org Isolation."""
    organization = Organization(
        id=uuid.uuid4(),
        slug=f"other-org-{uuid.uuid4().hex[:8]}",
        name="سازمان دوم",
        settings={},
        plan="pilot",
        is_active=True,
    )
    db_session.add(organization)
    await db_session.commit()
    await db_session.refresh(organization)
    return organization


async def _create_user(db_session: AsyncSession, org: Organization, role: str, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        org_id=org.id,
        email=email,
        full_name=f"کاربر {role}",
        hashed_password=hash_password("Password@123"),
        role=role,
        is_active=True,
        is_email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def org_admin_user(db_session: AsyncSession, org: Organization) -> User:
    return await _create_user(db_session, org, "org_admin", "org_admin@test.local")


@pytest_asyncio.fixture
async def employee_user(db_session: AsyncSession, org: Organization) -> User:
    return await _create_user(db_session, org, "employee", "employee@test.local")


@pytest_asyncio.fixture
async def super_admin_user(db_session: AsyncSession, org: Organization) -> User:
    return await _create_user(db_session, org, "super_admin", "super_admin@test.local")


async def _login(client: AsyncClient, email: str, password: str = "Password@123") -> str:
    res = await client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest_asyncio.fixture
async def org_admin_headers(client: AsyncClient, org_admin_user: User) -> dict:
    token = await _login(client, org_admin_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def employee_headers(client: AsyncClient, employee_user: User) -> dict:
    token = await _login(client, employee_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def super_admin_headers(client: AsyncClient, super_admin_user: User) -> dict:
    token = await _login(client, super_admin_user.email)
    return {"Authorization": f"Bearer {token}"}
