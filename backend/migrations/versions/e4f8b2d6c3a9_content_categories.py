"""content categories

Revision ID: e4f8b2d6c3a9
Revises: d3f7b1a4c8e2
Create Date: 2026-08-24 00:00:00.000000+00:00

توضیح:
    دسته‌بندی محتوا (course/article/podcast/book) — یک جدول content_categories
    (مشابه document_categories) + ستون contents.category_id (اختیاری، SET NULL
    در صورت حذف دسته).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4f8b2d6c3a9'
down_revision: Union[str, Sequence[str], None] = 'd3f7b1a4c8e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'content_categories',
        sa.Column('org_id', sa.UUID(), nullable=True, comment='NULL یعنی دسته‌بندی Public/General'),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_content_categories_org_id'), 'content_categories', ['org_id'], unique=False)

    op.add_column('contents', sa.Column('category_id', sa.UUID(), nullable=True, comment='دسته‌بندی محتوا — اختیاری، می‌تواند خالی باشد'))
    op.create_foreign_key(
        'fk_contents_category_id', 'contents', 'content_categories',
        ['category_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(op.f('ix_contents_category_id'), 'contents', ['category_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_contents_category_id'), table_name='contents')
    op.drop_constraint('fk_contents_category_id', 'contents', type_='foreignkey')
    op.drop_column('contents', 'category_id')

    op.drop_index(op.f('ix_content_categories_org_id'), table_name='content_categories')
    op.drop_table('content_categories')
