"""dynamic points policy (item overrides + group overrides)

Revision ID: c8f2a5d9e3b7
Revises: b7c3e1f4a2d8
Create Date: 2026-07-19 00:00:00.000000+00:00

توضیح:
    سیاست امتیاز سه‌لایه می‌شود: ۱) مقدار سراسری پیش‌فرض (point_rules،
    از قبل موجود) ۲) override اختصاصی خود موجودیت — ستون points_override
    روی quizzes/contents/content_items/program_steps/onboarding_programs
    ۳) override گروهی (نقش/واحد سازمانی) — جدول جدید point_group_overrides.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8f2a5d9e3b7'
down_revision: Union[str, Sequence[str], None] = 'b7c3e1f4a2d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('quizzes', sa.Column('points_override', sa.Integer(), nullable=True, comment='امتیاز اختصاصی این آزمون برای رویداد quiz_passed — null یعنی از مقدار سراسری استفاده شود'))
    op.add_column('contents', sa.Column('points_override', sa.Integer(), nullable=True, comment='امتیاز اختصاصی این محتوا برای رویداد content_completed — null یعنی از مقدار سراسری استفاده شود'))
    op.add_column('content_items', sa.Column('points_override', sa.Integer(), nullable=True, comment='امتیاز اختصاصی این آیتم برای رویداد content_item_completed — null یعنی از مقدار سراسری استفاده شود'))
    op.add_column('program_steps', sa.Column('points_override', sa.Integer(), nullable=True, comment='امتیاز اختصاصی این مرحله برای رویداد onboarding_step_completed — null یعنی از مقدار سراسری استفاده شود'))
    op.add_column('onboarding_programs', sa.Column('points_override', sa.Integer(), nullable=True, comment='امتیاز اختصاصی این برنامه برای رویداد onboarding_program_completed — null یعنی از مقدار سراسری استفاده شود'))

    op.create_table(
        'point_group_overrides',
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False, comment='role | department'),
        sa.Column('target_value', sa.String(length=255), nullable=False, comment='نام نقش برای role — UUID واحد سازمانی برای department'),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_type', 'target_type', 'target_value', name='uq_point_group_override'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('point_group_overrides')
    op.drop_column('onboarding_programs', 'points_override')
    op.drop_column('program_steps', 'points_override')
    op.drop_column('content_items', 'points_override')
    op.drop_column('contents', 'points_override')
    op.drop_column('quizzes', 'points_override')
