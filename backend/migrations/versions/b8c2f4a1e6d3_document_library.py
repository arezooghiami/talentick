"""document library (categories, documents, document_targets)

Revision ID: b8c2f4a1e6d3
Revises: e7f1a2b3c4d5
Create Date: 2026-07-15 00:00:00.000000+00:00

توضیح:
    کتابخانه‌ی اسناد سازمانی (قوانین/آیین‌نامه‌ها/مستندات) — سه جدول:
    document_categories (دسته‌بندی)، documents (خود سند — فایل واقعی در
    MinIO است)، document_targets (قانون دسترسی بر اساس واحد/نقش — OR).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8c2f4a1e6d3'
down_revision: Union[str, Sequence[str], None] = 'e7f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document_categories',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_document_categories_org_id'), 'document_categories', ['org_id'], unique=False)

    op.create_table(
        'documents',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_url', sa.String(length=1000), nullable=False),
        sa.Column('file_name', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True, comment='حجم به بایت'),
        sa.Column('file_type', sa.String(length=20), nullable=True, comment='پسوند فایل — pdf | doc | docx | ...'),
        sa.Column('uploaded_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['document_categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_org_id'), 'documents', ['org_id'], unique=False)
    op.create_index(op.f('ix_documents_category_id'), 'documents', ['category_id'], unique=False)

    op.create_table(
        'document_targets',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False, comment='department | role'),
        sa.Column(
            'target_value', sa.String(length=255), nullable=False,
            comment='UUID برای department — نام role برای role',
        ),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'target_type', 'target_value', name='uq_document_target'),
    )
    op.create_index(op.f('ix_document_targets_org_id'), 'document_targets', ['org_id'], unique=False)
    op.create_index(op.f('ix_document_targets_document_id'), 'document_targets', ['document_id'], unique=False)
    op.create_index(
        'ix_document_targets_lookup', 'document_targets',
        ['document_id', 'target_type', 'target_value'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_document_targets_lookup', table_name='document_targets')
    op.drop_index(op.f('ix_document_targets_document_id'), table_name='document_targets')
    op.drop_index(op.f('ix_document_targets_org_id'), table_name='document_targets')
    op.drop_table('document_targets')

    op.drop_index(op.f('ix_documents_category_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_org_id'), table_name='documents')
    op.drop_table('documents')

    op.drop_index(op.f('ix_document_categories_org_id'), table_name='document_categories')
    op.drop_table('document_categories')
