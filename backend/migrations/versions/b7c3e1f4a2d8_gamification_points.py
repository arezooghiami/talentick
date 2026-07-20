"""gamification points (point_rules, points_ledger)

Revision ID: b7c3e1f4a2d8
Revises: a4d7e2f9b6c1
Create Date: 2026-07-19 00:00:00.000000+00:00

توضیح:
    سیستم امتیاز سبک — point_rules (سراسری، مدیریت super_admin) مقدار
    امتیاز هر نوع اتفاق تکمیل را نگه می‌دارد؛ points_ledger دفترکل
    add-only است که هر بار امتیاز به یک کاربر اهدا می‌شود یک ردیف در آن
    ثبت می‌شود — با UNIQUE(user_id, event_type, reference_id) که هم
    idempotency را تضمین می‌کند هم «فقط بار اول قبولی آزمون» را.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c3e1f4a2d8'
down_revision: Union[str, Sequence[str], None] = 'a4d7e2f9b6c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'point_rules',
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_type', name='uq_point_rules_event_type'),
    )

    op.create_table(
        'points_ledger',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('reference_id', sa.UUID(), nullable=False, comment='شناسه‌ی موجودیت مرتبط — content_item/content/quiz/program_step/onboarding_program'),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'event_type', 'reference_id', name='uq_points_ledger_event'),
    )
    op.create_index(op.f('ix_points_ledger_org_id'), 'points_ledger', ['org_id'], unique=False)
    op.create_index(op.f('ix_points_ledger_user_id'), 'points_ledger', ['user_id'], unique=False)

    # ─── قوانین امتیاز پیش‌فرض ─────────────────────────────────────────
    point_rules = sa.table(
        'point_rules',
        sa.column('id', sa.UUID()),
        sa.column('event_type', sa.String()),
        sa.column('points', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
    )
    op.bulk_insert(point_rules, [
        {'id': '22222222-2222-2222-2222-222222222201', 'event_type': 'content_item_completed', 'points': 5, 'is_active': True},
        {'id': '22222222-2222-2222-2222-222222222202', 'event_type': 'content_completed', 'points': 20, 'is_active': True},
        {'id': '22222222-2222-2222-2222-222222222203', 'event_type': 'quiz_passed', 'points': 15, 'is_active': True},
        {'id': '22222222-2222-2222-2222-222222222204', 'event_type': 'onboarding_step_completed', 'points': 10, 'is_active': True},
        {'id': '22222222-2222-2222-2222-222222222205', 'event_type': 'onboarding_program_completed', 'points': 50, 'is_active': True},
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_points_ledger_user_id'), table_name='points_ledger')
    op.drop_index(op.f('ix_points_ledger_org_id'), table_name='points_ledger')
    op.drop_table('points_ledger')
    op.drop_table('point_rules')
