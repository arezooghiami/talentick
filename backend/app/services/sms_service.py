"""
Talentick — SMS Service (Stub)
================================
زیرساخت ارسال پیامک — فعلاً بدون اتصال به هیچ provider واقعی (طبق تصمیم
محصول). فقط پیام را لاگ می‌کند تا در توسعه/تست قابل مشاهده باشد.

وقتی provider واقعی (کاوه‌نگار/ملی‌پیامک/...) انتخاب شد، فقط بدنه‌ی
send_sms باید عوض شود — امضای تابع برای بقیه‌ی کد (auth_service) ثابت
می‌ماند.
"""

import logging

logger = logging.getLogger(__name__)


async def send_sms(phone: str, message: str) -> None:
    """ارسال پیامک — فعلاً فقط لاگ (بدون provider واقعی)."""
    logger.info("SMS به %s: %s", phone, message)
