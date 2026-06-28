"""
Talentick — Database Connection
================================
Async SQLAlchemy engine + session factory.

قوانین:
- هرگز session را در خارج از dependency inject شده استفاده نکنید
- هر request یک session جداگانه دریافت می‌کند
- session به صورت خودکار بسته می‌شود (async context manager)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# ─── Async Engine ────────────────────────────────────────────────────────────
# echo=True در development برای دیدن SQL queries مفید است
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,          # بررسی اتصال قبل از استفاده
    pool_recycle=3600,           # بازیابی connection بعد از 1 ساعت
    echo=settings.debug,         # در production: False
)

# ─── Session Factory ─────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,      # برای جلوگیری از lazy loading بعد از commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — یک async session می‌دهد.

    استفاده در router:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...

    session به صورت خودکار commit یا rollback می‌شود.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()