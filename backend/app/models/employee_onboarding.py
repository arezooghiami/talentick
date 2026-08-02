"""
Talentick — Employee Onboarding Document Models
===================================================
جداول: employee_document_types, employee_document_submissions

کاتالوگ مدارک موردنیاز هر سازمان + مدرک/مقدار ثبت‌شده‌ی هر کاربر.

معماری (بعد از بازطراحی مشترک با ماژول آنبوردینگ): «مسیر ورود کارمند
جدید» دیگر یک Config/Progress جداگانه نیست — خودش یک
app.models.onboarding.OnboardingProgram با purpose="employee_onboarding"
است (همان موتور Program → Step → Enrollment → StepProgress که برای
مسیرهای یادگیری هم استفاده می‌شود). این دو جدولِ این فایل فقط پشتوانه‌ی
واقعیِ نوع مرحله‌ی "document_upload" هستند — تکمیل آن مرحله خودکار از
روی همین دو جدول محاسبه می‌شود (services/onboarding_service.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# وضعیت مدرک آپلودشده — فاز فعلی فقط "approved" صادر می‌شود (تأیید
# خودکار در لحظه‌ی ثبت، بدون گردش‌کار بازبینی دستی)؛ under_review و
# rejected برای فعال‌سازی بازبینی دستی در فاز بعد رزرو شده‌اند — بدون
# نیاز به تغییر اساسی دیتابیس آن زمان.
DOCUMENT_SUBMISSION_STATUSES = ("approved", "under_review", "rejected")

# نوع ورودی یک قلم از کاتالوگ مدارک — همه‌چیز فایل نیست (مثال واقعی:
# «شماره حساب بانک سینا» متن است، نه فایل). "file" = آپلود فایل، "text" =
# یک مقدار متنی/عددی ساده (بدون فرمت اجباری در V1).
DOCUMENT_INPUT_TYPES = ("file", "text")


class EmployeeDocumentType(UUIDMixin, TimestampMixin, Base):
    """
    کاتالوگ مدارک موردنیاز سازمان (مثال: عکس پرسنلی، کارت ملی، شماره
    حساب بانکی) — مستقل از هر Program خاص، چون طبق اسپک «هر سازمان
    مدارک موردنیاز خود را تعریف کند» (نه هر مسیر). مدیریت فقط توسط
    super_admin/org_admin.
    """

    __tablename__ = "employee_document_types"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="محل توضیح گزینه‌های جایگزین («پایان خدمت یا کارت معافیت») و کمیت («۲ قطعه») — به‌جای مدل‌سازی ساختاری در V1"
    )
    input_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="file",
        comment="file | text — مثال text: شماره حساب بانکی. یک اسلات آپلود/مقدار به‌ازای هر ردیف در V1."
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_extensions: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list,
        comment="فقط برای input_type=file — زیرمجموعه‌ی ALLOWED_EXTENSIONS سراسری در core/storage.py؛ خالی یعنی همه‌ی فرمت‌های سراسری مجازند"
    )
    max_size_mb: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="فقط برای input_type=file — null یعنی از سقف سراسری (MAX_FILE_SIZE_MB) استفاده شود"
    )
    template_file_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="فقط برای input_type=file — فرم خام/نمونه که ادمین یک‌بار آپلود می‌کند تا کارمند دانلود/پر/بارگذاری کند (مثال: فرم افتتاح حساب بانکی)"
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ─── Relationships ────────────────────────────────────────────────────
    submissions: Mapped[list["EmployeeDocumentSubmission"]] = relationship(
        back_populates="document_type"
    )

    def __repr__(self) -> str:
        return f"<EmployeeDocumentType name={self.name!r}>"


class EmployeeDocumentSubmission(UUIDMixin, TimestampMixin, Base):
    """
    مدرک/مقدار ثبت‌شده‌ی یک کاربر برای یک قلم مشخص از کاتالوگ.

    بسته به document_type.input_type دقیقاً یکی از (file_url) یا
    (text_value) پر می‌شود — enforcement در employee_onboarding_service،
    نه DB Constraint (هم‌راستا با سبک بقیه‌ی این ماژول).

    فاز فعلی: تأیید خودکار در لحظه‌ی ثبت (status="approved" بلافاصله،
    reviewed_by=None یعنی تأییدِ سیستم نه انسان) — ستون‌های بازبینی دستی
    از قبل در schema حاضرند تا فعال‌سازی‌شان در فاز بعد نیاز به تغییر
    اساسی دیتابیس نداشته باشد.

    ثبت مجدد همین سطر را overwrite می‌کند — تاریخچه‌ی نسخه‌های قبلی
    نگه‌داشته نمی‌شود (تصمیم آگاهانه برای سادگی در V1).

    هر بار این سطر تغییر می‌کند، services/onboarding_service.py
    (sync_document_upload_steps_for_user) مراحل نوع document_upload این
    کاربر را در تمام Enrollment هایش (هر Programی) بازمحاسبه می‌کند.
    """

    __tablename__ = "employee_document_submissions"

    __table_args__ = (
        UniqueConstraint("user_id", "document_type_id", name="uq_employee_document_submissions_user_type"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employee_document_types.id"),
        nullable=False,
        index=True,
    )

    # ─── input_type=file ────────────────────────────────────────────────
    file_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="حجم به بایت")
    file_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ─── input_type=text (مثال: شماره حساب بانکی) ──────────────────────
    text_value: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="approved",
        comment="approved | under_review | rejected — فاز فعلی: همیشه approved (تأیید خودکار)"
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="NULL یعنی تأیید خودکار سیستم — رزرو برای فاز بازبینی دستی آینده",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ─── Relationships ────────────────────────────────────────────────────
    document_type: Mapped["EmployeeDocumentType"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"<EmployeeDocumentSubmission user={self.user_id} type={self.document_type_id} status={self.status!r}>"
