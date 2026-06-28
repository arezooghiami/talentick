"""
Talentick — Auth Service
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.user import User


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """ایمیل و پسورد را بررسی می‌کند."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def build_token(user: User) -> dict:
    """Access token برای کاربر می‌سازد."""
    token = create_access_token({
        "sub": str(user.id),
        "org_id": str(user.org_id),
        "role": user.role,
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "org_id": str(user.org_id),
        "role": user.role,
        "full_name": user.full_name,
    }