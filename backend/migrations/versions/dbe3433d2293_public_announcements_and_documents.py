"""general/public announcements + documents — nullable org_id

Revision ID: dbe3433d2293
Revises: 2ed174dc9e0d
Create Date: 2026-07-28 00:00:00.000000+00:00

توضیح (فاز ۲.۲ از فیچر General/Public — دامنه‌ی Announcement + Document):
    org_id روی announcements/document_categories/documents از NOT NULL به
    nullable تغییر می‌کند. NULL یعنی اطلاعیه/دسته‌بندی/سند Public/General
    است — فقط super_admin می‌سازد.

    announcement_targets و document_targets عمداً دست‌نخورده (همچنان
    NOT NULL) می‌مانند — چون موجودیت Public هرگز target ندارد
    (اعتبارسنجی در announcement_service/document_service). سند Public
    همچنین هرگز category_id ندارد (اعتبارسنجی مشابه در document_service)
    — بنابراین document_categories.org_id نیز عملاً هرگز NULL درج
    نمی‌شود، اما برای هم‌ساختاری با documents.org_id و انعطاف احتمالی
    آینده nullable شد.

    داده‌های فعلی دست‌نخورده می‌مانند — هیچ رکورد موجودی org_id=NULL ندارد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'dbe3433d2293'
down_revision: Union[str, Sequence[str], None] = '2ed174dc9e0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NULLABLE_TABLES_COLUMNS = [
    ('announcements', 'org_id'),
    ('document_categories', 'org_id'),
    ('documents', 'org_id'),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, column in _NULLABLE_TABLES_COLUMNS:
        op.alter_column(table, column, existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    for table, column in reversed(_NULLABLE_TABLES_COLUMNS):
        op.alter_column(table, column, existing_type=sa.UUID(), nullable=False)
