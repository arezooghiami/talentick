"""ticketing (categories, tickets, message threads, access grants)

Revision ID: a4d7e2f9b6c1
Revises: c9d3e5f7a1b4
Create Date: 2026-07-19 00:00:00.000000+00:00

توضیح:
    سیستم تیکتینگ — کارمند درخواست/بازخورد ثبت می‌کند، ادمین‌ها پاسخ
    می‌دهند. چهار جدول: ticket_categories (سراسری، مدیریت super_admin)،
    tickets (خود تیکت)، ticket_messages (ترد گفتگو)، و
    ticket_access_grants (اجازه‌ی دسترسی اضافه به نقش/کاربر خاص که
    super_admin تعیین می‌کند — فراتر از پیش‌فرض org_admin/super_admin).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a4d7e2f9b6c1'
down_revision: Union[str, Sequence[str], None] = 'c9d3e5f7a1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ticket_categories',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'tickets',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('related_content_id', sa.UUID(), nullable=True, comment='اتصال اختیاری به یک محتوای مشخص — مثلاً نظر درباره‌ی یک دوره'),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open', comment='open | answered | closed'),
        sa.Column('satisfaction_rating', sa.Integer(), nullable=True, comment='۱ تا ۵ — فقط وقتی کارمند خودش با رضایت می‌بندد'),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['ticket_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['related_content_id'], ['contents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tickets_org_id'), 'tickets', ['org_id'], unique=False)
    op.create_index(op.f('ix_tickets_created_by'), 'tickets', ['created_by'], unique=False)

    op.create_table(
        'ticket_messages',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('ticket_id', sa.UUID(), nullable=False),
        sa.Column('sender_id', sa.UUID(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ticket_messages_org_id'), 'ticket_messages', ['org_id'], unique=False)
    op.create_index(op.f('ix_ticket_messages_ticket_id'), 'ticket_messages', ['ticket_id'], unique=False)

    op.create_table(
        'ticket_access_grants',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('grant_type', sa.String(length=10), nullable=False, comment='role | user'),
        sa.Column('role', sa.String(length=20), nullable=True, comment='فقط وقتی grant_type=role'),
        sa.Column('user_id', sa.UUID(), nullable=True, comment='فقط وقتی grant_type=user'),
        sa.Column('granted_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ticket_access_grants_org_id'), 'ticket_access_grants', ['org_id'], unique=False)

    # ─── دسته‌بندی‌های پیش‌فرض ─────────────────────────────────────────
    ticket_categories = sa.table(
        'ticket_categories',
        sa.column('id', sa.UUID()),
        sa.column('name', sa.String()),
        sa.column('order_index', sa.Integer()),
        sa.column('is_active', sa.Boolean()),
    )
    op.bulk_insert(ticket_categories, [
        {'id': '11111111-1111-1111-1111-111111111101', 'name': 'درخواست دوره‌ی جدید', 'order_index': 1, 'is_active': True},
        {'id': '11111111-1111-1111-1111-111111111102', 'name': 'بازخورد درباره‌ی محتوا', 'order_index': 2, 'is_active': True},
        {'id': '11111111-1111-1111-1111-111111111103', 'name': 'مشکل فنی', 'order_index': 3, 'is_active': True},
        {'id': '11111111-1111-1111-1111-111111111104', 'name': 'سایر', 'order_index': 4, 'is_active': True},
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ticket_access_grants_org_id'), table_name='ticket_access_grants')
    op.drop_table('ticket_access_grants')

    op.drop_index(op.f('ix_ticket_messages_ticket_id'), table_name='ticket_messages')
    op.drop_index(op.f('ix_ticket_messages_org_id'), table_name='ticket_messages')
    op.drop_table('ticket_messages')

    op.drop_index(op.f('ix_tickets_created_by'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_org_id'), table_name='tickets')
    op.drop_table('tickets')

    op.drop_table('ticket_categories')
