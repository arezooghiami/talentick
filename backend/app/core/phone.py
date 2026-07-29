"""
Talentick — Phone Normalization
==================================
اعتبارسنجی و نرمال‌سازی شماره موبایل ایران — تنها فرمت پشتیبانی‌شده.

فرمت‌های ورودی پذیرفته‌شده: 09xxxxxxxxx | +989xxxxxxxxx | 00989xxxxxxxxx
(با فاصله/خط‌تیره‌ی احتمالی بین ارقام) — خروجی همیشه +98XXXXXXXXXX است.
"""

import re

_MOBILE_CORE = re.compile(r"^9\d{9}$")


def normalize_phone(raw: str) -> str:
    """
    شماره موبایل را به فرمت یکتای +98XXXXXXXXXX تبدیل می‌کند.

    ورودی نامعتبر (فرمت اشتباه، غیر ایران، طول نادرست) → ValueError،
    تا لایه‌ی صدا زننده (Pydantic validator یا service) آن را به خطای
    مناسب (422 یا BadRequestError) تبدیل کند.
    """
    cleaned = re.sub(r"[\s\-()]", "", raw or "")

    if cleaned.startswith("+98"):
        core = cleaned[3:]
    elif cleaned.startswith("0098"):
        core = cleaned[4:]
    elif cleaned.startswith("098"):
        core = cleaned[2:]
    elif cleaned.startswith("0"):
        core = cleaned[1:]
    else:
        core = cleaned

    if not _MOBILE_CORE.match(core):
        raise ValueError("شماره موبایل نامعتبر است — فرمت صحیح: 09xxxxxxxxx")

    return f"+98{core}"
