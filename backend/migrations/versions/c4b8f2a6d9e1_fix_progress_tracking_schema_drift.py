"""fix progress-tracking schema drift (missing table + columns)

Revision ID: c4b8f2a6d9e1
Revises: f3a9c1d2e4b7
Create Date: 2026-07-14 00:00:00.000000+00:00

توضیح — باگ حیاتی از قبل موجود (کشف‌شده حین ممیزی/تکمیل V1):

    مدل SQLAlchemy برای UserContentProgress سه ستون status،
    total_view_time_seconds و last_viewed_at دارد که هرگز در migration
    اولیه (5d427d3827dd) ساخته نشدند. همچنین کل جدول UserItemProgress
    (که progress_service.py برای پیگیری پیشرفت هر آیتم محتوا استفاده
    می‌کند) هیچ‌وقت migrate نشده بود.

    نتیجه: هر تلاش برای مشاهده محتوا (`POST /api/me/contents/{id}/start`)،
    به‌روزرسانی پیشرفت آیتم، یا هر گزارش (`/api/reports/*`,
    `/api/dashboard/*`) که به UserContentProgress نیاز دارد، با
    UndefinedColumnError/UndefinedTableError روی دیتابیس واقعی fail
    می‌شد — یعنی زیرسیستم Progress Tracking و بخش عمده‌ی گزارش‌گیری در
    عمل هرگز کار نمی‌کردند، صرف‌نظر از درستی کد Python.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4b8f2a6d9e1'
down_revision: Union[str, Sequence[str], None] = 'f3a9c1d2e4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ─── تکمیل ستون‌های کم‌شده روی user_content_progress ──────────────────
    op.add_column(
        'user_content_progress',
        sa.Column(
            'status', sa.String(length=20), nullable=False,
            server_default='not_started',
            comment='not_started | in_progress | completed',
        ),
    )
    op.add_column(
        'user_content_progress',
        sa.Column(
            'total_view_time_seconds', sa.Integer(), nullable=False,
            server_default='0', comment='مجموع زمان مشاهده (ثانیه) — برای گزارش BI',
        ),
    )
    op.add_column(
        'user_content_progress',
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # ─── ساخت جدول user_item_progress (کاملاً غایب بود) ───────────────────
    op.create_table(
        'user_item_progress',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('content_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column(
            'status', sa.String(length=20), nullable=False,
            server_default='not_started',
            comment='not_started | in_progress | completed',
        ),
        sa.Column(
            'progress_pct', sa.Integer(), nullable=False, server_default='0',
            comment='درصد پیشرفت این آیتم 0-100',
        ),
        sa.Column(
            'last_position', sa.Integer(), nullable=True,
            comment='آخرین محل مشاهده — مثلاً ثانیه ویدیو یا شماره صفحه PDF',
        ),
        sa.Column(
            'view_time_seconds', sa.Integer(), nullable=False, server_default='0',
            comment='مجموع زمان مشاهده این آیتم (ثانیه)',
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['contents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_id'], ['content_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'item_id', name='uq_user_item'),
    )
    op.create_index(op.f('ix_user_item_progress_content_id'), 'user_item_progress', ['content_id'], unique=False)
    op.create_index(op.f('ix_user_item_progress_item_id'), 'user_item_progress', ['item_id'], unique=False)
    op.create_index(op.f('ix_user_item_progress_org_id'), 'user_item_progress', ['org_id'], unique=False)
    op.create_index(op.f('ix_user_item_progress_user_id'), 'user_item_progress', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_user_item_progress_user_id'), table_name='user_item_progress')
    op.drop_index(op.f('ix_user_item_progress_org_id'), table_name='user_item_progress')
    op.drop_index(op.f('ix_user_item_progress_item_id'), table_name='user_item_progress')
    op.drop_index(op.f('ix_user_item_progress_content_id'), table_name='user_item_progress')
    op.drop_table('user_item_progress')

    op.drop_column('user_content_progress', 'last_viewed_at')
    op.drop_column('user_content_progress', 'total_view_time_seconds')
    op.drop_column('user_content_progress', 'status')
