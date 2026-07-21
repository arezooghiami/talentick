"""
Talentick — Point Wallet Service
=====================================
تنها نقطه‌ی مجاز برای تغییر PointWallet و ثبت PointsLedgerEntry — بخش
سوم/چهارم اسپک («هیچ امتیازی نباید بدون ثبت تراکنش تغییر کند»).

apply_ledger_entry() هسته‌ی این ماژول است:
  - ردیف PointWallet مربوط به کاربر را قفل می‌کند (SELECT ... FOR UPDATE)
    تا race condition (دو تراکنش هم‌زمان) امکان‌پذیر نباشد.
  - balance_before/after را از روی موجودی *قفل‌شده‌ی همین لحظه* محاسبه
    می‌کند (نه از روی SUM کل ledger — سریع‌تر و از race condition مصون).
  - با INSERT ... ON CONFLICT DO NOTHING روی UNIQUE(user_id, event_type,
    reference_id) atomically idempotent است — اگر ردیف تکراری بود، نه
    ledger و نه wallet تغییر نمی‌کنند.
  - commit نمی‌کند (فقط flush) — caller باید در همان تراکنشی که خودِ
    اتفاق را ثبت می‌کند صدا بزند تا اتمیک باشند.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.models.points import TRANSACTION_TYPES, PointsLedgerEntry, PointWallet


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_wallet(db: AsyncSession, user_id: uuid.UUID) -> PointWallet | None:
    """خواندن کیف‌پول بدون قفل — برای نمایش (نه برای تغییر)."""
    return await db.scalar(select(PointWallet).where(PointWallet.user_id == user_id))


async def _get_wallet_locked(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID) -> PointWallet:
    wallet = await db.scalar(
        select(PointWallet).where(PointWallet.user_id == user_id).with_for_update()
    )
    if wallet:
        return wallet

    stmt = pg_insert(PointWallet).values(
        id=uuid.uuid4(), user_id=user_id, org_id=org_id,
    ).on_conflict_do_nothing(index_elements=["user_id"])
    await db.execute(stmt)
    await db.flush()

    wallet = await db.scalar(
        select(PointWallet).where(PointWallet.user_id == user_id).with_for_update()
    )
    assert wallet is not None
    return wallet


async def _next_transaction_number(db: AsyncSession) -> str:
    seq_val = await db.scalar(select(func.nextval("points_ledger_txn_seq")))
    return f"TXN-{seq_val:08d}"


async def apply_ledger_entry(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    transaction_type: str,
    points: int,
    event_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    description: str | None = None,
    points_source: str | None = None,
) -> PointsLedgerEntry | None:
    """
    تنها راه ثبت یک تراکنش امتیاز + به‌روزرسانی کیف‌پول.

    برمی‌گرداند None اگر points صفر باشد (هیچ تراکنشی برای صفر ثبت
    نمی‌شود) یا اگر idempotency (user_id, event_type, reference_id)
    از قبل برآورده شده باشد.
    """
    if transaction_type not in TRANSACTION_TYPES:
        raise ValueError(f"transaction_type نامعتبر: {transaction_type}")
    if points == 0:
        return None

    resolved_event_type = event_type or transaction_type
    resolved_reference_id = reference_id or uuid.uuid4()

    wallet = await _get_wallet_locked(db, user_id, org_id)

    balance_before = wallet.current_balance
    balance_after = balance_before + points
    transaction_number = await _next_transaction_number(db)

    stmt = pg_insert(PointsLedgerEntry).values(
        id=uuid.uuid4(),
        transaction_number=transaction_number,
        transaction_type=transaction_type,
        org_id=org_id,
        user_id=user_id,
        event_type=resolved_event_type,
        reference_id=resolved_reference_id,
        points=points,
        balance_before=balance_before,
        balance_after=balance_after,
        points_source=points_source,
        description=description,
        created_by=created_by,
        created_at=_now(),
    ).on_conflict_do_nothing(constraint="uq_points_ledger_event")
    result = await db.execute(stmt)
    await db.flush()

    if result.rowcount == 0:
        return None  # قبلاً برای همین سه‌تایی ثبت شده — idempotent no-op

    wallet.current_balance = balance_after
    if transaction_type == "expiration":
        wallet.total_expired += -points if points < 0 else 0
    elif points > 0:
        wallet.total_earned += points
    else:
        wallet.total_spent += -points
    await db.flush()

    entry = await db.scalar(
        select(PointsLedgerEntry).where(
            PointsLedgerEntry.user_id == user_id,
            PointsLedgerEntry.event_type == resolved_event_type,
            PointsLedgerEntry.reference_id == resolved_reference_id,
        )
    )
    return entry


async def adjust_pending(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID, delta: int) -> None:
    """تغییر pending_points (اطلاعاتی — امتیازی رزرو/قفل نمی‌شود) هنگام submit/خروج از وضعیت در-انتظار."""
    if delta == 0:
        return
    wallet = await _get_wallet_locked(db, user_id, org_id)
    wallet.pending_points = max(0, wallet.pending_points + delta)
    await db.flush()


async def mark_redeemed(db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID, points: int) -> None:
    """افزایش redeemed_points هنگام delivered شدن یک درخواست تبدیل — نه تراکنش امتیاز (کسر قبلاً هنگام approve ثبت شده)."""
    if points <= 0:
        return
    wallet = await _get_wallet_locked(db, user_id, org_id)
    wallet.redeemed_points += points
    await db.flush()
