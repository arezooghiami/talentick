"""galleries (photo collections: title/description/cover + ordered photos)

Revision ID: a7e2c5f9b3d6
Revises: f4a8c2e6b9d3
Create Date: 2026-08-03 00:00:00.000000+00:00

توضیح:
    گالری (مجموعه عکس) — خارج از سیستم محتوای آموزشی. دو جدول: galleries
    (خود گالری — عنوان/توضیحات/کاور/وضعیت فعال) و gallery_photos (عکس‌های
    داخل گالری با ترتیب نمایش). org_id روی galleries نال‌پذیر است —
    NULL یعنی گالری Public/General (هم‌ساختار با announcements/documents).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7e2c5f9b3d6'
down_revision: Union[str, Sequence[str], None] = 'f4a8c2e6b9d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'galleries',
        sa.Column('org_id', sa.UUID(), nullable=True, comment='NULL یعنی گالری Public/General (فقط super_admin می‌سازد)'),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cover_image_url', sa.String(length=1000), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_galleries_org_id'), 'galleries', ['org_id'], unique=False)

    op.create_table(
        'gallery_photos',
        sa.Column('gallery_id', sa.UUID(), nullable=False),
        sa.Column('image_url', sa.String(length=1000), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['gallery_id'], ['galleries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_gallery_photos_gallery_id'), 'gallery_photos', ['gallery_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_gallery_photos_gallery_id'), table_name='gallery_photos')
    op.drop_table('gallery_photos')

    op.drop_index(op.f('ix_galleries_org_id'), table_name='galleries')
    op.drop_table('galleries')
