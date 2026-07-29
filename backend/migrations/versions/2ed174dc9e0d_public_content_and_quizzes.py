"""general/public content + quizzes — nullable org_id

Revision ID: 2ed174dc9e0d
Revises: ee1b20412676
Create Date: 2026-07-28 00:00:00.000000+00:00

توضیح (فاز ۲.۱ از فیچر General/Public — دامنه‌ی Content + Quiz):
    org_id روی contents/content_items/user_content_progress/
    user_item_progress/quizzes/questions/quiz_attempts از NOT NULL به
    nullable تغییر می‌کند. NULL یعنی محتوا/آزمون Public/General است —
    فقط super_admin می‌سازد و بدون Targeting (content_targets) — همیشه
    برای همه (کاربران General + همه‌ی کاربران سازمان‌ها) قابل مشاهده است.

    content_targets عمداً دست‌نخورده (همچنان NOT NULL) می‌ماند — چون
    محتوای Public هرگز target ندارد (اعتبارسنجی در content_service).

    داده‌های فعلی دست‌نخورده می‌مانند — هیچ رکورد موجودی org_id=NULL ندارد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2ed174dc9e0d'
down_revision: Union[str, Sequence[str], None] = 'ee1b20412676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE_TABLES_COLUMNS = [
    ('contents', 'org_id'),
    ('content_items', 'org_id'),
    ('user_content_progress', 'org_id'),
    ('user_item_progress', 'org_id'),
    ('quizzes', 'org_id'),
    ('questions', 'org_id'),
    ('quiz_attempts', 'org_id'),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column in _NULLABLE_TABLES_COLUMNS:
        op.alter_column(table, column, existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in reversed(_NULLABLE_TABLES_COLUMNS):
        op.alter_column(table, column, existing_type=sa.UUID(), nullable=False)
