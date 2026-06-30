"""
Talentick — Department Service
=================================
CRUD واحدهای سازمانی + ساخت چارت درختی.

قانون: org_id همیشه فیلتر اصلی است — router مقدار درست را تعیین می‌کند.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Department
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentTreeNode,
    DepartmentUpdate,
)


async def _user_counts(db: AsyncSession, org_id: uuid.UUID) -> dict[str, int]:
    rows = await db.execute(
        select(User.dept_id, func.count())
        .where(User.org_id == org_id, User.dept_id.is_not(None))
        .group_by(User.dept_id)
    )
    return {str(dept_id): count for dept_id, count in rows.all()}


async def _to_response(db: AsyncSession, dept: Department, counts: dict[str, int] | None = None) -> DepartmentResponse:
    manager_name = None
    if dept.manager_id:
        manager = await db.get(User, dept.manager_id)
        manager_name = manager.full_name if manager else None
    if counts is None:
        counts = await _user_counts(db, dept.org_id)
    return DepartmentResponse(
        id=str(dept.id),
        org_id=str(dept.org_id),
        name=dept.name,
        description=dept.description,
        parent_id=str(dept.parent_id) if dept.parent_id else None,
        manager_id=str(dept.manager_id) if dept.manager_id else None,
        manager_name=manager_name,
        order_index=dept.order_index,
        is_active=dept.is_active,
        user_count=counts.get(str(dept.id), 0),
        created_at=dept.created_at,
    )


async def list_departments(db: AsyncSession, org_id: uuid.UUID) -> list[DepartmentResponse]:
    result = await db.execute(
        select(Department)
        .where(Department.org_id == org_id)
        .order_by(Department.order_index, Department.created_at)
    )
    depts = list(result.scalars().all())
    counts = await _user_counts(db, org_id)
    return [await _to_response(db, d, counts) for d in depts]


async def get_department(db: AsyncSession, dept_id: str) -> Department | None:
    try:
        did = uuid.UUID(dept_id)
    except ValueError:
        return None
    result = await db.execute(select(Department).where(Department.id == did))
    return result.scalar_one_or_none()


async def create_department(db: AsyncSession, org_id: uuid.UUID, data: DepartmentCreate) -> Department:
    dept = Department(
        id=uuid.uuid4(),
        org_id=org_id,
        name=data.name,
        description=data.description,
        parent_id=uuid.UUID(data.parent_id) if data.parent_id else None,
        manager_id=uuid.UUID(data.manager_id) if data.manager_id else None,
        order_index=data.order_index,
        is_active=True,
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


async def update_department(db: AsyncSession, dept: Department, data: DepartmentUpdate) -> Department:
    payload = data.model_dump(exclude_unset=True)
    for field in ("parent_id", "manager_id"):
        if field in payload:
            payload[field] = uuid.UUID(payload[field]) if payload[field] else None
    for field, value in payload.items():
        setattr(dept, field, value)
    await db.commit()
    await db.refresh(dept)
    return dept


async def delete_department(db: AsyncSession, dept: Department) -> None:
    """
    حذف واحد سازمانی.

    cascade مدل: positions زیرمجموعه حذف می‌شوند (cascade در رابطه تعریف شده)،
    و کاربران/زیرواحدهایی که dept_id/parent_id به این واحد اشاره دارند
    طبق FK با ondelete=SET NULL آزاد می‌شوند (حذف نمی‌شوند).
    """
    await db.delete(dept)
    await db.commit()


async def build_tree(db: AsyncSession, org_id: uuid.UUID) -> list[DepartmentTreeNode]:
    """درخت چارت سازمانی را از لیست مسطح می‌سازد."""
    result = await db.execute(
        select(Department)
        .where(Department.org_id == org_id)
        .order_by(Department.order_index, Department.created_at)
    )
    depts = list(result.scalars().all())
    counts = await _user_counts(db, org_id)

    manager_ids = {d.manager_id for d in depts if d.manager_id}
    manager_names: dict[str, str] = {}
    if manager_ids:
        rows = await db.execute(select(User).where(User.id.in_(manager_ids)))
        manager_names = {str(u.id): u.full_name for u in rows.scalars().all()}

    nodes: dict[str, DepartmentTreeNode] = {
        str(d.id): DepartmentTreeNode(
            id=str(d.id),
            name=d.name,
            manager_name=manager_names.get(str(d.manager_id)) if d.manager_id else None,
            user_count=counts.get(str(d.id), 0),
            is_active=d.is_active,
            children=[],
        )
        for d in depts
    }

    roots: list[DepartmentTreeNode] = []
    for d in depts:
        node = nodes[str(d.id)]
        parent_key = str(d.parent_id) if d.parent_id else None
        if parent_key and parent_key in nodes:
            nodes[parent_key].children.append(node)
        else:
            roots.append(node)
    return roots