"""users must_change_password flag

Revision ID: f3a9c1d2e4b7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 00:00:00.000000+00:00

توضیح:
    وقتی رمز عبور یک کاربر توسط شخص دیگری تنظیم می‌شود (ساخت دستی توسط
    ادمین، Import گروهی از Excel، یا Reset توسط ادمین)، آن رمز را خودِ
    ادمین می‌داند. برای جلوگیری از باقی‌ماندن دائمی این دانش نزد ادمین،
    ستون must_change_password اضافه می‌شود: تا وقتی True است، کاربر فقط
    به POST /api/auth/change-password و GET /api/auth/me و
    POST /api/auth/logout دسترسی دارد (enforcement در
    dependencies.get_current_user) — و باید ابتدا رمز را عوض کند.

    مقدار پیش‌فرض False است تا کاربرانِ از قبل موجود (که این ستون برایشان
    معنا ندارد) قفل نشوند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3a9c1d2e4b7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: افزودن users.must_change_password."""
    op.add_column(
        'users',
        sa.Column(
            'must_change_password',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment=(
                'True یعنی رمز توسط ادمین تنظیم شده و کاربر باید عوضش کند'
            ),
        ),
    )


def downgrade() -> None:
    """Downgrade schema: حذف users.must_change_password."""
    op.drop_column('users', 'must_change_password')
