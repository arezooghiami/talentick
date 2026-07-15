"""content sequential progress (ordered item lock)

Revision ID: e7f1a2b3c4d5
Revises: caba809a078c
Create Date: 2026-07-15 00:00:00.000000+00:00

توضیح:
    ستون sequential_progress به جدول contents اضافه می‌شود — سوئیچ
    دستیِ per-content برای «قفل ترتیبی آیتم‌ها»: وقتی True باشد، کاربر
    باید آیتم‌های محتوا (ویدیو/PDF/آزمون و ...) را دقیقاً به ترتیب
    order_index تکمیل کند و نمی‌تواند آیتم بعدی را قبل از تکمیل آیتم‌های
    قبلی ببیند/شروع کند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'caba809a078c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: افزودن ستون sequential_progress."""
    op.add_column(
        'contents',
        sa.Column(
            'sequential_progress', sa.Boolean(), nullable=False,
            server_default=sa.false(),
            comment='قفل ترتیبی آیتم‌ها — کاربر باید آیتم‌ها را دقیقاً به ترتیب order_index تکمیل کند',
        ),
    )


def downgrade() -> None:
    """Downgrade schema: حذف ستون sequential_progress."""
    op.drop_column('contents', 'sequential_progress')
