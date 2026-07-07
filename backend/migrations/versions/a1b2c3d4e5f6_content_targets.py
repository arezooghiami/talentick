"""content targets (targeted publishing: department/position/role/user)

Revision ID: a1b2c3d4e5f6
Revises: 902e98d3b8e4
Create Date: 2026-07-07 00:00:00.000000+00:00

توضیح:
    برای پیاده‌سازی «انتشار هدفمند محتوا» (سازمان/دپارتمان/پست/نقش/کاربر
    مشخص)، جدول content_targets اضافه می‌شود. هر سطر یک قانون هدف‌گذاری
    است. اگر برای یک محتوا هیچ سطری وجود نداشته باشد، یعنی آن محتوا برای
    کل سازمان قابل مشاهده است (سازگار با محتواهای قبلی).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '902e98d3b8e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: ساخت جدول content_targets."""
    op.create_table(
        'content_targets',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('content_id', sa.UUID(), nullable=False),
        sa.Column(
            'target_type', sa.String(length=20), nullable=False,
            comment='department | position | role | user',
        ),
        sa.Column(
            'target_value', sa.String(length=255), nullable=False,
            comment='UUID برای department/position/user — نام role برای role',
        ),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['contents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_id', 'target_type', 'target_value', name='uq_content_target'),
    )
    op.create_index(op.f('ix_content_targets_org_id'), 'content_targets', ['org_id'], unique=False)
    op.create_index(op.f('ix_content_targets_content_id'), 'content_targets', ['content_id'], unique=False)
    # ایندکس ترکیبی برای سریع کردن جستجوی «آیا این کاربر با یکی از هدف‌ها match می‌شود؟»
    op.create_index(
        'ix_content_targets_lookup', 'content_targets',
        ['content_id', 'target_type', 'target_value'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema: حذف جدول content_targets."""
    op.drop_index('ix_content_targets_lookup', table_name='content_targets')
    op.drop_index(op.f('ix_content_targets_content_id'), table_name='content_targets')
    op.drop_index(op.f('ix_content_targets_org_id'), table_name='content_targets')
    op.drop_table('content_targets')
