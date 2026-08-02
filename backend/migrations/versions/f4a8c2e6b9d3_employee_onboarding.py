"""employee onboarding — program purpose + document catalog

Revision ID: f4a8c2e6b9d3
Revises: 18dd8cc500d7
Create Date: 2026-08-01 00:00:00.000000+00:00

توضیح:
    فرآیند ورود کارمند جدید (Employee Onboarding) به‌عنوان یک ماژول
    کاملاً مستقل *محصولی* اضافه می‌شود، اما زیرساخت داده‌ای‌اش عمداً
    همان موتور مسیر/مرحله‌ی ماژول «آنبوردینگ» موجود (OnboardingProgram →
    ProgramStep → UserProgramEnrollment → UserStepProgress) است — بدون
    Duplicate Logic. تفکیک دو محصول («مسیرهای یادگیری» در برابر «ورود
    کارمند جدید») فقط با یک ستون تشخیص‌دهنده (`purpose`) روی
    onboarding_programs انجام می‌شود؛ در پنل ادمین و API دو بخش کاملاً
    جدا (فیلترشده با ?purpose=...) روی همین جدول‌ها کار می‌کنند.

    ۱) onboarding_programs.purpose (String, default='learning'):
       - 'learning'            → رفتار قبلی/فعلی، بدون تغییر
       - 'employee_onboarding' → مسیر ورود کارمند جدید — Gate در
         dependencies.py بر اساس Enrollment ناتمام در برنامه‌ای با این
         purpose مسدود می‌کند.

    ۲) نوع مرحله‌ی document_upload (از قبل در STEP_TYPES بود اما هرگز
       واقعاً کار نمی‌کرد — کلیک دستی «تکمیل» بدون هیچ آپلود واقعی) حالا
       واقعی می‌شود: تکمیلش خودکار از روی کاتالوگ مدارک سازمان محاسبه
       می‌شود (جدول‌های زیر)، نه با کلیک دستی.

    ۳) employee_document_types: کاتالوگ مدارک موردنیاز هر سازمان — مستقل
       از هر Program خاص (طبق اسپک: «هر سازمان مدارک موردنیاز خود را
       تعریف کند»، نه هر مسیر). دو نوع ورودی: file (آپلود) و text (مثال:
       شماره حساب بانکی).

    ۴) employee_document_submissions: مدرک/مقدار ثبت‌شده‌ی هر کاربر —
       تأیید خودکار در لحظه‌ی ثبت (بدون گردش‌کار بازبینی دستی در فاز
       فعلی؛ ستون‌های reviewed_by/reviewed_at/rejection_reason از قبل
       اضافه شده‌اند تا فعال‌سازی بازبینی دستی در آینده migration
       ساختاری جدید نخواهد).

    نکته: نسخه‌ی قبلی این migration شامل جدول‌های employee_onboarding_configs
    و employee_onboarding_progress و دو ستون require_org_intro/
    require_document_upload روی users بود — همه‌ی این‌ها بعد از بازطراحی
    مشترک با ماژول آنبوردینگ حذف شدند (منبع حقیقت الان مستقیماً
    UserProgramEnrollment است، نه یک Progress جدا). چون این migration
    هنوز به هیچ دیتابیس واقعی apply نشده بود، به‌جای یک migration جدید
    برای «حذف»، همین فایل بازنویسی شد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f4a8c2e6b9d3'
down_revision: Union[str, Sequence[str], None] = '18dd8cc500d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ─── onboarding_programs.purpose ────────────────────────────────────────
    op.add_column(
        'onboarding_programs',
        sa.Column(
            'purpose', sa.String(length=30), nullable=False, server_default='learning',
            comment='learning | employee_onboarding — همان موتور، دو محصول مستقل در UI/API',
        ),
    )
    op.create_index(
        op.f('ix_onboarding_programs_purpose'), 'onboarding_programs', ['purpose'], unique=False,
    )

    # ─── employee_document_types ────────────────────────────────────────────
    op.create_table(
        'employee_document_types',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column(
            'description', sa.Text(), nullable=True,
            comment='محل توضیح گزینه‌های جایگزین و کمیت — به‌جای مدل‌سازی ساختاری در V1',
        ),
        sa.Column(
            'input_type', sa.String(length=20), nullable=False, server_default='file',
            comment='file | text — مثال text: شماره حساب بانکی',
        ),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            'allowed_extensions', postgresql.ARRAY(sa.String()), nullable=False,
            comment='فقط برای input_type=file — زیرمجموعه‌ی ALLOWED_EXTENSIONS سراسری',
        ),
        sa.Column('max_size_mb', sa.Integer(), nullable=True, comment='فقط برای input_type=file — null یعنی از سقف سراسری استفاده شود'),
        sa.Column(
            'template_file_url', sa.String(length=1000), nullable=True,
            comment='فقط برای input_type=file — فرم خام برای دانلود/پر/بارگذاری مجدد',
        ),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_employee_document_types_org_id'),
        'employee_document_types', ['org_id'], unique=False,
    )

    # ─── employee_document_submissions ──────────────────────────────────────
    op.create_table(
        'employee_document_submissions',
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('document_type_id', sa.UUID(), nullable=False),
        sa.Column('file_url', sa.String(length=1000), nullable=True, comment='فقط برای input_type=file'),
        sa.Column('file_name', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True, comment='حجم به بایت'),
        sa.Column('file_type', sa.String(length=20), nullable=True),
        sa.Column('text_value', sa.String(length=1000), nullable=True, comment='فقط برای input_type=text'),
        sa.Column(
            'status', sa.String(length=20), nullable=False, server_default='approved',
            comment='approved | under_review | rejected — فاز فعلی: تأیید خودکار در لحظه‌ی ثبت',
        ),
        sa.Column(
            'reviewed_by', sa.UUID(), nullable=True,
            comment='NULL یعنی تأیید خودکار سیستم (بدون بازبین انسانی) — رزرو برای فاز بازبینی دستی آینده',
        ),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_type_id'], ['employee_document_types.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'document_type_id', name='uq_employee_document_submissions_user_type'),
    )
    op.create_index(
        op.f('ix_employee_document_submissions_org_id'),
        'employee_document_submissions', ['org_id'], unique=False,
    )
    op.create_index(
        op.f('ix_employee_document_submissions_user_id'),
        'employee_document_submissions', ['user_id'], unique=False,
    )
    op.create_index(
        op.f('ix_employee_document_submissions_document_type_id'),
        'employee_document_submissions', ['document_type_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_employee_document_submissions_document_type_id'), table_name='employee_document_submissions')
    op.drop_index(op.f('ix_employee_document_submissions_user_id'), table_name='employee_document_submissions')
    op.drop_index(op.f('ix_employee_document_submissions_org_id'), table_name='employee_document_submissions')
    op.drop_table('employee_document_submissions')

    op.drop_index(op.f('ix_employee_document_types_org_id'), table_name='employee_document_types')
    op.drop_table('employee_document_types')

    op.drop_index(op.f('ix_onboarding_programs_purpose'), table_name='onboarding_programs')
    op.drop_column('onboarding_programs', 'purpose')
