"""
Talentick — Gamification Audit Service
===========================================
بخش یازدهم اسپک — Audit Trail. هر تغییر در Ruleها/Rewardها و هر تصمیم
روی درخواست‌های تبدیل امتیاز باید یک ردیف اینجا ثبت کند. commit نمی‌کند
(فقط flush) — caller در تراکنش خودش commit می‌کند.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.points import GamificationAuditLog


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def log(
    db: AsyncSession,
    *,
    org_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> GamificationAuditLog:
    entry = GamificationAuditLog(
        id=uuid.uuid4(), org_id=org_id, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id, before=before, after=after,
        note=note, created_at=_now(),
    )
    db.add(entry)
    await db.flush()
    return entry
