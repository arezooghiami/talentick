"""users has_seen_welcome flag

Revision ID: c1a9f5e7d2b4
Revises: a7e2c5f9b3d6
Create Date: 2026-08-09 00:00:00.000000+00:00

توضیح:
    ستون has_seen_welcome برای تشخیص «آیا کاربر ۳ صفحه‌ی welcome را دیده یا
    نه» اضافه می‌شود — صرفاً یک flag ساده سمت فرانت است (تصمیم gate کردن
    endpoint ها گرفته نشد، برخلاف must_change_password/employee_onboarding).

    مقدار پیش‌فرض ستون False است (کاربران جدید welcome را می‌بینند)، اما
    کاربران از قبل موجود بلافاصله بعد از افزودن ستون به True backfill
    می‌شوند — چون این‌ها از قبل با سیستم آشنا هستند و نباید صفحات welcome
    برایشان به‌صورت غیرمنتظره ظاهر شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1a9f5e7d2b4'
down_revision: Union[str, Sequence[str], None] = 'a7e2c5f9b3d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: افزودن users.has_seen_welcome + backfill کاربران موجود."""
    op.add_column(
        'users',
        sa.Column(
            'has_seen_welcome',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment=(
                'True یعنی کاربر ۳ صفحه‌ی welcome را دیده — فقط برای تصمیم '
                'نمایش سمت فرانت است'
            ),
        ),
    )
    op.execute("UPDATE users SET has_seen_welcome = true")


def downgrade() -> None:
    """Downgrade schema: حذف users.has_seen_welcome."""
    op.drop_column('users', 'has_seen_welcome')
