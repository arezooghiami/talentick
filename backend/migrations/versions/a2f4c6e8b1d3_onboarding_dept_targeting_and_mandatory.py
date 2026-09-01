"""employee onboarding — per-department targeting + mandatory enrollment flag

Revision ID: a2f4c6e8b1d3
Revises: e4f8b2d6c3a9
Create Date: 2026-09-01 00:00:00.000000+00:00

توضیح:
    دو ستون افزایشی برای فیچر «آنبوردینگ کارمند» (purpose=employee_onboarding):

    - onboarding_programs.target_dept_ids — آرایه‌ی UUID واحدهای هدف. لیست خالی
      یعنی همه‌ی اعضای سازمان مسیر را در GET /api/me/onboarding می‌بینند.
      (ستون تک‌مقداری target_dept_id دست‌نخورده می‌ماند — مخصوص «مسیر یادگیری».)

    - user_program_enrollments.is_mandatory — True یعنی ثبت‌نام از مسیر «کارمند
      جدید» فرم کاربر است و Gate داشبورد را فعال می‌کند. ثبت‌نام داوطلبانه‌ای که
      کاربر خودش با تکمیل یک مرحله می‌سازد False است.
      Backfill: همه‌ی ثبت‌نام‌های فعلیِ برنامه‌های employee_onboarding → True
      (تا امروز فقط با انتساب صریح ادمین ساخته شده‌اند).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a2f4c6e8b1d3"
down_revision: Union[str, Sequence[str], None] = "e4f8b2d6c3a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "onboarding_programs",
        sa.Column(
            "target_dept_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
            comment="واحدهای هدف (فقط employee_onboarding) — لیست خالی یعنی همه‌ی واحدها",
        ),
    )
    op.alter_column("onboarding_programs", "target_dept_ids", server_default=None)

    op.add_column(
        "user_program_enrollments",
        sa.Column(
            "is_mandatory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True یعنی ثبت‌نام «کارمند جدید» و Gate داشبورد را فعال می‌کند",
        ),
    )
    op.execute(
        "UPDATE user_program_enrollments e SET is_mandatory = true "
        "FROM onboarding_programs p "
        "WHERE p.id = e.program_id AND p.purpose = 'employee_onboarding'"
    )
    op.alter_column("user_program_enrollments", "is_mandatory", server_default=None)


def downgrade() -> None:
    op.drop_column("user_program_enrollments", "is_mandatory")
    op.drop_column("onboarding_programs", "target_dept_ids")
