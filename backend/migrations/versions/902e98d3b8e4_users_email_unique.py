"""users email unique constraint

Revision ID: 902e98d3b8e4
Revises: 5d427d3827dd
Create Date: 2026-07-06 00:00:00.000000+00:00

توضیح:
    ستون users.email از نظر منطق کسب‌وکار باید در کل پلتفرم یکتا باشد
    (طبق کامنت مدل)، اما تا پیش از این migration، فقط یک index معمولی
    (unique=False) روی آن وجود داشت و یکتایی صرفاً در سطح اپلیکیشن چک
    می‌شد — یعنی در شرایط race condition (دو request همزمان با یک ایمیل)
    امکان ثبت دو کاربر با ایمیل یکسان وجود داشت.

    این migration ایندکس قدیمی را با یک UNIQUE index جایگزین می‌کند.

⚠️ هشدار قبل از اجرا در محیطی با داده‌ی واقعی:
    اگر از قبل رکوردهای تکراری با ایمیل یکسان در جدول users وجود داشته
    باشد، این migration با خطای duplicate key شکست می‌خورد. پیش از اجرا
    این کوئری را برای شناسایی موارد تکراری اجرا کنید:

        SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

    و تکراری‌ها را دستی رفع کنید (تغییر ایمیل یا غیرفعال/حذف کاربر تکراری)،
    سپس migration را اجرا کنید.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '902e98d3b8e4'
down_revision: Union[str, Sequence[str], None] = '5d427d3827dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: تبدیل ix_users_email به UNIQUE index."""
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema: بازگشت به index معمولی (غیر یکتا)."""
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)
