"""content category many-to-many

Revision ID: b3f6a9d2c7e4
Revises: a2f4c6e8b1d3
Create Date: 2026-09-05 00:00:00.000000+00:00

توضیح:
    تبدیل رابطه‌ی محتوا/دسته‌بندی از یک‌به‌چند (contents.category_id) به
    چندبه‌چند — یک محتوا حالا می‌تواند عضو صفر، یک یا چند دسته باشد.
    جدول واسط content_category_links ساخته می‌شود، داده‌های قبلی
    category_id به آن منتقل می‌شود و ستون/FK/index قدیمی حذف می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3f6a9d2c7e4'
down_revision: Union[str, Sequence[str], None] = 'a2f4c6e8b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'content_category_links',
        sa.Column('content_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['contents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['content_categories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('content_id', 'category_id'),
    )

    op.execute(
        """
        INSERT INTO content_category_links (content_id, category_id)
        SELECT id, category_id FROM contents WHERE category_id IS NOT NULL
        """
    )

    op.drop_index(op.f('ix_contents_category_id'), table_name='contents')
    op.drop_constraint('fk_contents_category_id', 'contents', type_='foreignkey')
    op.drop_column('contents', 'category_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('contents', sa.Column('category_id', sa.UUID(), nullable=True, comment='دسته‌بندی محتوا — اختیاری، می‌تواند خالی باشد'))
    op.create_foreign_key(
        'fk_contents_category_id', 'contents', 'content_categories',
        ['category_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(op.f('ix_contents_category_id'), 'contents', ['category_id'], unique=False)

    # فقط اولین دسته‌ی هر محتوا برگردانده می‌شود — این تبدیل ذاتاً lossy است
    op.execute(
        """
        UPDATE contents SET category_id = sub.category_id
        FROM (
            SELECT DISTINCT ON (content_id) content_id, category_id
            FROM content_category_links
            ORDER BY content_id, category_id
        ) AS sub
        WHERE contents.id = sub.content_id
        """
    )

    op.drop_table('content_category_links')
