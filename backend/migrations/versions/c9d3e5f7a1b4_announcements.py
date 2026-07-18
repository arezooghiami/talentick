"""announcements (single-file notice board: image/video)

Revision ID: c9d3e5f7a1b4
Revises: b8c2f4a1e6d3
Create Date: 2026-07-15 00:00:00.000000+00:00

توضیح:
    اطلاعیه‌ی تک‌فایلی (عکس/ویدیو) خارج از سیستم محتوای آموزشی — برای
    اطلاع‌رسانی سریع در صفحه‌ی خانه‌ی کارمند. دو جدول: announcements
    (خود اطلاعیه) و announcement_targets (قانون دسترسی واحد/نقش — OR،
    هم‌ساختار با document_targets).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c9d3e5f7a1b4'
down_revision: Union[str, Sequence[str], None] = 'b8c2f4a1e6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'announcements',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(length=1000), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False, comment='image | video'),
        sa.Column('file_name', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True, comment='حجم به بایت'),
        sa.Column(
            'starts_at', sa.DateTime(timezone=True), nullable=True,
            comment='شروع بازه‌ی نمایش — خالی یعنی از هم‌اکنون',
        ),
        sa.Column(
            'ends_at', sa.DateTime(timezone=True), nullable=True,
            comment='پایان بازه‌ی نمایش — خالی یعنی نامحدود',
        ),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_announcements_org_id'), 'announcements', ['org_id'], unique=False)

    op.create_table(
        'announcement_targets',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('announcement_id', sa.UUID(), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False, comment='department | role'),
        sa.Column(
            'target_value', sa.String(length=255), nullable=False,
            comment='UUID برای department — نام role برای role',
        ),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['announcement_id'], ['announcements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('announcement_id', 'target_type', 'target_value', name='uq_announcement_target'),
    )
    op.create_index(op.f('ix_announcement_targets_org_id'), 'announcement_targets', ['org_id'], unique=False)
    op.create_index(op.f('ix_announcement_targets_announcement_id'), 'announcement_targets', ['announcement_id'], unique=False)
    op.create_index(
        'ix_announcement_targets_lookup', 'announcement_targets',
        ['announcement_id', 'target_type', 'target_value'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_announcement_targets_lookup', table_name='announcement_targets')
    op.drop_index(op.f('ix_announcement_targets_announcement_id'), table_name='announcement_targets')
    op.drop_index(op.f('ix_announcement_targets_org_id'), table_name='announcement_targets')
    op.drop_table('announcement_targets')

    op.drop_index(op.f('ix_announcements_org_id'), table_name='announcements')
    op.drop_table('announcements')
