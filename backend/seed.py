"""
Talentick — Seed Script
ساخت سوپر ادمین اولیه سیستم

اجرا:
    python seed.py

این اسکریپت:
1. یک سازمان Talentick می‌سازد (برای خود سوپر ادمین)
2. یک کاربر super_admin می‌سازد
"""
import asyncio
import uuid
import os
import sys

# مسیر پروژه را به path اضافه می‌کنیم
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.organization import Organization
from app.models.user import User
from app.core.security import hash_password

# ─── تنظیمات سوپر ادمین اولیه ──────────────────────────────────────────────
SUPER_ADMIN_EMAIL = "admin@talentick.ir"
SUPER_ADMIN_PASSWORD = "Admin@1234"
SUPER_ADMIN_NAME = "سوپر ادمین"


async def seed():
    async with AsyncSessionLocal() as db:
        # بررسی وجود super_admin
        result = await db.execute(
            select(User).where(User.email == SUPER_ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"✅ سوپر ادمین قبلاً ساخته شده: {SUPER_ADMIN_EMAIL}")
            return

        # ساخت سازمان Talentick (برای خود سیستم)
        org = Organization(
            id=uuid.uuid4(),
            slug="talentick-system",
            name="Talentick",
            name_en="Talentick",
            description="سازمان داخلی سیستم Talentick",
            settings={},
            plan="pilot",
            is_active=True,
        )
        db.add(org)
        await db.flush()

        # ساخت سوپر ادمین
        admin = User(
            id=uuid.uuid4(),
            org_id=org.id,
            email=SUPER_ADMIN_EMAIL,
            full_name=SUPER_ADMIN_NAME,
            hashed_password=hash_password(SUPER_ADMIN_PASSWORD),
            role="super_admin",
            is_active=True,
            is_email_verified=True,
        )
        db.add(admin)
        await db.commit()

        print("=" * 50)
        print("✅ سوپر ادمین با موفقیت ساخته شد")
        print(f"   ایمیل:  {SUPER_ADMIN_EMAIL}")
        print(f"   پسورد:  {SUPER_ADMIN_PASSWORD}")
        print("=" * 50)
        print("⚠️  پسورد را بعد از اولین ورود تغییر دهید!")


if __name__ == "__main__":
    asyncio.run(seed())
