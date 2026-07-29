"""general/public onboarding programs — nullable org_id

Revision ID: 13792830dd7c
Revises: dbe3433d2293
Create Date: 2026-07-28 00:00:00.000000+00:00

توضیح (فاز ۲.۳ از فیچر General/Public — دامنه‌ی Onboarding):
    org_id روی onboarding_programs/program_steps/user_program_enrollments/
    user_step_progress از NOT NULL به nullable تغییر می‌کند. NULL یعنی
    برنامه‌ی آشنایی Public/General است — فقط super_admin می‌سازد و
    target_dept_id آن باید همیشه خالی باشد (چون دپارتمان مفهومی
    سازمانی است) — اعتبارسنجی در onboarding_service.

    کاربران General هم اکنون در برنامه‌های Public پیش‌فرض (is_default)
    خودکار ثبت‌نام می‌شوند (auto_enroll_new_user) — دقیقاً مثل کاربران
    سازمانی که در برنامه‌های سازمان خودشان + برنامه‌های Public خودکار
    ثبت‌نام می‌شوند.

    داده‌های فعلی دست‌نخورده می‌مانند — هیچ رکورد موجودی org_id=NULL ندارد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '13792830dd7c'
down_revision: Union[str, Sequence[str], None] = 'dbe3433d2293'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE_TABLES_COLUMNS = [
    ('onboarding_programs', 'org_id'),
    ('program_steps', 'org_id'),
    ('user_program_enrollments', 'org_id'),
    ('user_step_progress', 'org_id'),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column in _NULLABLE_TABLES_COLUMNS:
        op.alter_column(table, column, existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in reversed(_NULLABLE_TABLES_COLUMNS):
        op.alter_column(table, column, existing_type=sa.UUID(), nullable=False)
