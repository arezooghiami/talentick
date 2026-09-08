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

from app.models.organization import Department, Position
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentMemberNode,
    DepartmentReorderItem,
    DepartmentResponse,
    DepartmentTreeNode,
    DepartmentUpdate,
)


class ReorderError(ValueError):
    """خطای اعتبارسنجی هنگام بازچینش درخت — پیام برای نمایش به کاربر مناسب است."""


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


async def reorder_departments(
    db: AsyncSession, org_id: uuid.UUID, items: list[DepartmentReorderItem]
) -> None:
    """
    والد (parent_id) و ترتیب نمایش (order_index) چند واحد را یکجا به‌روزرسانی می‌کند.

    خروجی مستقیم کشیدن‌ورهاکردن در نمای درختی است. قبل از اعمال:
    - همه‌ی id ها و parent_id ها باید متعلق به همین سازمان باشند.
    - نتیجه‌ی نهایی نباید حلقه (چرخه) بسازد — واحد نمی‌تواند زیرمجموعه‌ی
      خودش یا یکی از زیرمجموعه‌هایش شود.
    کل تغییر در یک transaction اعمال می‌شود (all-or-nothing).
    """
    result = await db.execute(select(Department).where(Department.org_id == org_id))
    by_id = {str(d.id): d for d in result.scalars().all()}

    # نقشه‌ی والدِ پیشنهادی برای همه‌ی واحدها (شروع از وضعیت فعلی)
    proposed_parent: dict[str, str | None] = {
        did: (str(d.parent_id) if d.parent_id else None) for did, d in by_id.items()
    }

    for it in items:
        if it.id not in by_id:
            raise ReorderError("واحدی در این سازمان یافت نشد")
        if it.parent_id is not None:
            if it.parent_id not in by_id:
                raise ReorderError("واحد مادر معتبر نیست")
            if it.parent_id == it.id:
                raise ReorderError("یک واحد نمی‌تواند مادر خودش باشد")
        proposed_parent[it.id] = it.parent_id

    # تشخیص چرخه — از هر گره به سمت ریشه بالا می‌رویم
    for start in by_id:
        seen: set[str] = set()
        cur: str | None = start
        while cur is not None:
            if cur in seen:
                raise ReorderError("این جابه‌جایی یک حلقه در ساختار سازمانی می‌سازد")
            seen.add(cur)
            cur = proposed_parent.get(cur)

    for it in items:
        dept = by_id[it.id]
        dept.parent_id = uuid.UUID(it.parent_id) if it.parent_id else None
        dept.order_index = it.order_index

    await db.commit()


def _sort_member_nodes(nodes: list[DepartmentMemberNode]) -> None:
    """افرادِ هم‌رده: مدیرِ واحد اول، سپس سطح پست نزولی، سپس نام."""
    nodes.sort(key=lambda n: (not n.is_manager, -n.position_level, n.full_name))
    for n in nodes:
        _sort_member_nodes(n.children)


async def _members_by_dept(
    db: AsyncSession, org_id: uuid.UUID, dept_manager_id: dict[str, uuid.UUID | None]
) -> dict[str, list[DepartmentMemberNode]]:
    """
    برای هر واحد، افرادِ آن را به‌صورت تودرتو بر اساس «سطح پستِ سازمانی»
    برمی‌گرداند (سطح بالاتر = رتبه بالاتر؛ ۸ = مدیرعامل). فقط کاربران
    فعالِ دارای `dept_id`.

    منطق چیدمان داخل هر واحد:
      • افرادِ بالاترین سطحِ موجود، ریشه‌های واحد هستند.
      • هر فردِ دیگر زیر «نزدیک‌ترین سطحِ بالاتر» در همان واحد می‌نشیند.
      • رفعِ ابهام وقتی چند نفر در آن سطحِ بالاتر هستند:
          ۱) اگر یکی از آن‌ها «مدیر واحد» است → زیرِ او.
          ۲) وگرنه اگر `manager_id` فرد به یکی از آن‌ها اشاره می‌کند → زیرِ همان.
          ۳) وگرنه → زیرِ اولین نفرِ آن سطح (به ترتیب نام).
      • «مدیر واحد» همیشه یک ریشه است (زیرِ کسی نمی‌رود)؛ اگر سطحِ او از
        همه بالاتر نباشد، افرادِ هم‌سطح یا بالاترش هم کنارش ریشه می‌شوند.
    """
    rows = await db.execute(
        select(User).where(
            User.org_id == org_id,
            User.dept_id.is_not(None),
            User.is_active.is_(True),
        )
    )
    users = list(rows.scalars().all())
    if not users:
        return {}

    pos_ids = {u.position_id for u in users if u.position_id}
    positions: dict[uuid.UUID, Position] = {}
    if pos_ids:
        prows = await db.execute(select(Position).where(Position.id.in_(pos_ids)))
        positions = {p.id: p for p in prows.scalars().all()}

    def _level(u: User) -> int:
        pos = positions.get(u.position_id) if u.position_id else None
        return pos.level if pos else 0

    by_dept: dict[str, list[User]] = {}
    for u in users:
        by_dept.setdefault(str(u.dept_id), []).append(u)

    result: dict[str, list[DepartmentMemberNode]] = {}
    for dept_id, dept_users in by_dept.items():
        mgr_id = dept_manager_id.get(dept_id)
        levels_desc = sorted({_level(u) for u in dept_users}, reverse=True)

        node_map: dict[uuid.UUID, DepartmentMemberNode] = {
            u.id: DepartmentMemberNode(
                id=str(u.id),
                full_name=u.full_name,
                avatar_url=u.avatar_url,
                position_name=(
                    positions[u.position_id].name
                    if u.position_id in positions else None
                ),
                position_level=_level(u),
                is_manager=(mgr_id is not None and u.id == mgr_id),
                is_active=u.is_active,
                children=[],
            )
            for u in dept_users
        }

        roots: list[DepartmentMemberNode] = []
        for u in dept_users:
            lvl = _level(u)
            higher_levels = [x for x in levels_desc if x > lvl]

            # مدیر واحد، و هرکس در بالاترین سطحِ موجود → ریشه‌ی واحد
            if u.id == mgr_id or not higher_levels:
                roots.append(node_map[u.id])
                continue

            parent_level = min(higher_levels)  # نزدیک‌ترین سطحِ بالاتر
            candidates = [
                c for c in dept_users if _level(c) == parent_level and c.id != u.id
            ]
            # قانون ۱ — مدیر واحد در میان کاندیداها
            parent = next((c for c in candidates if c.id == mgr_id), None)
            # قانون ۲ — مدیر مستقیمِ فرد در میان کاندیداها
            if parent is None and u.manager_id is not None:
                parent = next((c for c in candidates if c.id == u.manager_id), None)
            # قانون ۳ — اولین نفر به ترتیب نام
            if parent is None:
                parent = sorted(candidates, key=lambda c: c.full_name)[0]

            node_map[parent.id].children.append(node_map[u.id])

        _sort_member_nodes(roots)
        result[dept_id] = roots

    return result


async def build_tree(
    db: AsyncSession, org_id: uuid.UUID, include_members: bool = False
) -> list[DepartmentTreeNode]:
    """
    درخت چارت سازمانی را از لیست مسطح می‌سازد.

    با `include_members=True` افرادِ هر واحد هم به‌صورت تودرتو (بر اساس
    سطح پستِ سازمانی) در فیلد `members` هر گره قرار می‌گیرند — مخصوص پنل ادمین.
    """
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

    members_by_dept: dict[str, list[DepartmentMemberNode]] = {}
    if include_members:
        members_by_dept = await _members_by_dept(
            db, org_id, {str(d.id): d.manager_id for d in depts}
        )

    nodes: dict[str, DepartmentTreeNode] = {
        str(d.id): DepartmentTreeNode(
            id=str(d.id),
            name=d.name,
            manager_name=manager_names.get(str(d.manager_id)) if d.manager_id else None,
            user_count=counts.get(str(d.id), 0),
            is_active=d.is_active,
            children=[],
            members=members_by_dept.get(str(d.id), []),
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