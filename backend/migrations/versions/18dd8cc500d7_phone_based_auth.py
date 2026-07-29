"""phone-based auth — phone unique/required, email optional, otp_codes

Revision ID: 18dd8cc500d7
Revises: 13792830dd7c
Create Date: 2026-07-29 00:00:00.000000+00:00

توضیح:
    مهاجرت رویه‌ی لاگین از ایمیل به شماره موبایل:

    ۱. users.email از NOT NULL به nullable تغییر می‌کند — ایمیل دیگر
       اجباری نیست (لاگین اصلی از طریق موبایل است). ایندکس یکتای موجود
       (از migration 902e98d3b8e4) دست‌نخورده می‌ماند — Postgres به چند
       رکورد با email=NULL در یک unique index اجازه می‌دهد.
    ۲. users.phone (که تا امروز nullable و بدون ایندکس/یکتایی بود) به
       NOT NULL + UNIQUE index تغییر می‌کند — شماره موبایل شناسه‌ی اصلی
       یکتای سیستم می‌شود.
    ۳. جدول جدید otp_codes برای کدهای یک‌بارمصرف پیامکی (فعلاً فقط
       فراموشی رمز عبور — purpose قابل توسعه برای مصارف آینده).

⚠️ هشدار قبل از اجرا در محیطی با داده‌ی واقعی:
    چون phone تا امروز اختیاری بوده، ممکن است رکوردهایی با phone=NULL یا
    شماره‌های تکراری در جدول users وجود داشته باشد. پیش از اجرا این
    کوئری‌ها را برای شناسایی موارد مشکل‌دار اجرا کنید:

        SELECT id, email FROM users WHERE phone IS NULL;
        SELECT phone, COUNT(*) FROM users WHERE phone IS NOT NULL
            GROUP BY phone HAVING COUNT(*) > 1;

    این migration برای رکوردهای phone IS NULL به‌صورت خودکار یک مقدار
    Placeholder یکتا (+980000<۴ رقم اول id>) می‌گذارد تا NOT NULL/UNIQUE
    شکست نخورد — این‌ها واقعی نیستند و باید توسط ادمین با شماره‌ی موبایل
    واقعی جایگزین شوند (تا آن زمان، آن کاربران فقط با ایمیل — در صورت
    وجود — می‌توانند لاگین کنند). تکراری‌های واقعی (غیر NULL) باید پیش از
    اجرا دستی رفع شوند، وگرنه migration با خطای duplicate key شکست
    می‌خورد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '18dd8cc500d7'
down_revision: Union[str, Sequence[str], None] = '13792830dd7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('users', 'email', existing_type=sa.String(length=320), nullable=True)

    # بک‌فیل موقت برای رکوردهای بدون شماره موبایل — نیاز به اصلاح دستی توسط ادمین
    op.execute(
        "UPDATE users SET phone = '+980000' || substring(id::text, 1, 4) "
        "WHERE phone IS NULL"
    )

    op.alter_column(
        'users', 'phone',
        existing_type=sa.String(length=50),
        type_=sa.String(length=20),
        nullable=False,
    )
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)

    op.create_table(
        'otp_codes',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('purpose', sa.String(length=50), nullable=False, server_default='password_reset'),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_otp_codes_user_id'), 'otp_codes', ['user_id'], unique=False)
    op.create_index(op.f('ix_otp_codes_purpose'), 'otp_codes', ['purpose'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_otp_codes_purpose'), table_name='otp_codes')
    op.drop_index(op.f('ix_otp_codes_user_id'), table_name='otp_codes')
    op.drop_table('otp_codes')

    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.alter_column(
        'users', 'phone',
        existing_type=sa.String(length=20),
        type_=sa.String(length=50),
        nullable=True,
    )

    op.alter_column('users', 'email', existing_type=sa.String(length=320), nullable=False)
