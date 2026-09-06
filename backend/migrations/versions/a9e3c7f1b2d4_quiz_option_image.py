"""quiz question_options.image_url — گزینه‌ی تصویری

Revision ID: a9e3c7f1b2d4
Revises: b3f6a9d2c7e4
Create Date: 2026-09-06 00:00:00.000000+00:00

توضیح:
    ستون nullable جدید `image_url` روی question_options اضافه می‌شود تا
    نوع سوال جدید `single_image_choice` (منطق تک‌گزینه‌ای، ولی هر گزینه یک
    تصویر با کپشن متنی اختیاری) پشتیبانی شود.

    همچنین `body` گزینه از NOT NULL به «NOT NULL با default=''» تغییر
    می‌کند — برای گزینه‌ی تصویری متن اختیاری است. داده‌های فعلی دست‌نخورده
    می‌مانند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9e3c7f1b2d4'
down_revision: Union[str, Sequence[str], None] = 'b3f6a9d2c7e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'question_options',
        sa.Column('image_url', sa.Text(), nullable=True),
    )
    op.alter_column(
        'question_options', 'body',
        existing_type=sa.Text(),
        nullable=False,
        server_default='',
    )


def downgrade() -> None:
    op.alter_column(
        'question_options', 'body',
        existing_type=sa.Text(),
        nullable=False,
        server_default=None,
    )
    op.drop_column('question_options', 'image_url')
