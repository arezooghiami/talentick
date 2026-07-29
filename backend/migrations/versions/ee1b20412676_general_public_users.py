"""general/public users — nullable org_id on users + refresh_tokens

Revision ID: ee1b20412676
Revises: d4e6a2f8c1b9
Create Date: 2026-07-28 00:00:00.000000+00:00

توضیح (فاز ۱ از فیچر General/Public):
    مقدمه‌ی زیرساختی برای کاربران بدون سازمان (General/Public):

    ۱. users.org_id از NOT NULL به nullable تغییر می‌کند — کاربر General
       کسی است که org_id او NULL باشد.
    ۲. یک CheckConstraint اضافه می‌شود که تضمین می‌کند کاربر General
       همیشه role='employee' باشد (نقش‌های مدیریتی بدون سازمان بی‌معنی‌اند).
       محدودیت‌های dept_id/position_id/manager_id=NULL برای کاربر General
       عمداً در همین migration به‌صورت DB Constraint اعمال نمی‌شوند — طبق
       تصمیم محصول، این‌ها فقط در لایه‌ی سرویس (user_service) اعمال
       می‌شوند تا برای توسعه‌های بعدی انعطاف‌پذیرتر باشد.
    ۳. refresh_tokens.org_id هم nullable می‌شود — چون هنگام لاگین کاربر
       General مستقیماً از user.org_id (که NULL است) پر می‌شود.

    داده‌های فعلی دست‌نخورده می‌مانند — هیچ رکورد موجودی org_id=NULL ندارد،
    پس این migration روی داده‌های فعلی بدون ریسک است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ee1b20412676'
down_revision: Union[str, Sequence[str], None] = 'd4e6a2f8c1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('users', 'org_id', existing_type=sa.UUID(), nullable=True)
    op.alter_column('refresh_tokens', 'org_id', existing_type=sa.UUID(), nullable=True)

    op.create_check_constraint(
        'ck_users_general_user_is_employee',
        'users',
        "org_id IS NOT NULL OR role = 'employee'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_users_general_user_is_employee', 'users', type_='check')

    op.alter_column('refresh_tokens', 'org_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('users', 'org_id', existing_type=sa.UUID(), nullable=False)
