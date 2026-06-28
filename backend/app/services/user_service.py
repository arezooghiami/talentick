"""
Talentick — User Service
"""
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def list_users(db: AsyncSession, org_id: uuid.UUID | None = None) -> list[User]:
    q = select(User).order_by(User.created_at.desc())
    if org_id:
        q = q.where(User.org_id == org_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        id=uuid.uuid4(),
        org_id=data.org_id,
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        phone=data.phone,
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.flush()
    return user


async def delete_user(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.flush()
