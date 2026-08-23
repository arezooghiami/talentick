"""user_program_enrollments cancelled_at (soft-cancel)

Revision ID: d3f7b1a4c8e2
Revises: c1a9f5e7d2b4
Create Date: 2026-08-23 00:00:00.000000+00:00

توضیح:
    ستون cancelled_at به user_program_enrollments اضافه می‌شود تا وقتی
    ادمین چک‌باکس Employee Onboarding را در فرم ویرایش کاربر بردارد، بتوان
    Enrollment موجود را به‌صورت نرم (بدون حذف رکورد و تاریخچه‌ی
    UserStepProgress) غیرفعال کرد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd3f7b1a4c8e2'
down_revision: Union[str, Sequence[str], None] = 'c1a9f5e7d2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: افزودن user_program_enrollments.cancelled_at."""
    op.add_column(
        'user_program_enrollments',
        sa.Column(
            'cancelled_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                'غیرفعال‌سازی نرم — وقتی ادمین ثبت‌نام Employee Onboarding '
                'را از فرم ویرایش کاربر برمی‌دارد'
            ),
        ),
    )


def downgrade() -> None:
    """Downgrade schema: حذف user_program_enrollments.cancelled_at."""
    op.drop_column('user_program_enrollments', 'cancelled_at')
