"""add missing FK constraint on content_items.quiz_id

Revision ID: d1e5a7c3b9f2
Revises: c4b8f2a6d9e1
Create Date: 2026-07-14 00:00:00.000000+00:00

توضیح:
    content_items.quiz_id از ابتدا فقط یک comment داشت («شناسه Quiz اگر
    type=quiz_ref باشد») بدون اینکه واقعاً یک ForeignKeyConstraint به
    quizzes.id باشد — یعنی می‌شد یک quiz_id غیرموجود در آن ثبت کرد. حالا
    که ماژول Quiz به‌طور کامل پیاده‌سازی شده (routers/quizzes.py)، این
    ارتباط واقعاً استفاده می‌شود، پس یکپارچگی مرجع (Referential
    Integrity) آن هم باید در سطح دیتابیس تضمین شود.

    ondelete=SET NULL — حذف یک Quiz نباید ContentItem مرتبط را حذف کند؛
    فقط ارجاعش پاک می‌شود (مشابه الگوی program_steps.quiz_id).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd1e5a7c3b9f2'
down_revision: Union[str, Sequence[str], None] = 'c4b8f2a6d9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_foreign_key(
        'content_items_quiz_id_fkey',
        'content_items', 'quizzes',
        ['quiz_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('content_items_quiz_id_fkey', 'content_items', type_='foreignkey')
