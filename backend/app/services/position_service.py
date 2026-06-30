"""
Talentick — Position Service
===============================
CRUD پست‌های سازمانی.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Department, Position
from app.models.user import User
from app.schemas.position import PositionCreate, PositionResponse, PositionUpdate


async def _user_counts(db: AsyncSession, org_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(User.position_id, func.count())
        .where(User.org_id == org_id, User.position_id.is_not(None))
        .group_by(User.position_id)
    )
    return {str(pid): count for pid, count in rows.all()}


async def to_response(db: AsyncSession, pos: Position, counts: dict[str, int] | None = None) -> PositionResponse:
    dept_name = None
    if pos.dept_id:
        dept = await db.get(Department, pos.dept_id)
        dept_name = dept.name if dept else None
    if counts is None:
        counts = await _user_counts(db, pos.org_id)
    return PositionResponse(
        id=str(pos.id),
        org_id=str(pos.org_id),
        dept_id=str(pos.dept_id) if pos.dept_id else None,
        dept_name=dept_name,
        name=pos.name,
        description=pos.description,
        level=pos.level,
        is_active=pos.is_active,
        user_count=counts.get(str(pos.id), 0),
        created_at=pos.created_at,
    )


async def list_positions(db: AsyncSession, org_id: uuid.UUID, dept_id: str | None = None) -> list[PositionResponse]:
    q = select(Position).where(Position.org_id == org_id)
    if dept_id:
        q = q.where(Position.dept_id == uuid.UUID(dept_id))
    result = await db.execute(q.order_by(Position.level.desc(), Position.created_at))
    positions = list(result.scalars().all())
    counts = await _user_counts(db, org_id)
    return [await to_response(db, p, counts) for p in positions]


async def get_position(db: AsyncSession, position_id: str) -> Position | None:
    try:
        pid = uuid.UUID(position_id)
    except ValueError:
        return None
    result = await db.execute(select(Position).where(Position.id == pid))
    return result.scalar_one_or_none()


async def create_position(db: AsyncSession, org_id: uuid.UUID, data: PositionCreate) -> Position:
    pos = Position(
        id=uuid.uuid4(),
        org_id=org_id,
        dept_id=uuid.UUID(data.dept_id) if data.dept_id else None,
        name=data.name,
        description=data.description,
        level=data.level,
        is_active=True,
    )
    db.add(pos)
    await db.commit()
    await db.refresh(pos)
    return pos


async def update_position(db: AsyncSession, pos: Position, data: PositionUpdate) -> Position:
    payload = data.model_dump(exclude_unset=True)
    if "dept_id" in payload:
        payload["dept_id"] = uuid.UUID(payload["dept_id"]) if payload["dept_id"] else None
    for field, value in payload.items():
        setattr(pos, field, value)
    await db.commit()
    await db.refresh(pos)
    return pos


async def delete_position(db: AsyncSession, pos: Position) -> None:
    await db.delete(pos)
    await db.commit()