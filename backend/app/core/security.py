"""
Talentick — Security Utilities
================================
JWT token ساخت/اعتبارسنجی و hash کردن پسورد.

قوانین:
- هرگز پسورد plain text ذخیره نکنید
- Access token کوتاه‌مدت (60 دقیقه)
- Refresh token بلندمدت (30 روز) — در DB ذخیره می‌شود
- org_id همیشه در JWT payload است
"""

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import UnauthorizedError

# ─── Password Hashing ────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """پسورد را با bcrypt hash می‌کند."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """پسورد ورودی را با hash مقایسه می‌کند."""
    return _pwd_context.verify(plain_password, hashed_password)


_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_temp_password(length: int = 14) -> str:
    """
    رمز موقت تصادفی و امن می‌سازد — برای زمانی که ادمین رمز کاربری را
    می‌سازد/Reset می‌کند و باید آن را دستی (بدون ایمیل) به کاربر بدهد.

    از secrets.choice (CSPRNG) استفاده می‌شود — نه random ماژول معمولی.
    فقط حروف/عدد (بدون کاراکتر خاص) تا کپی/تایپ دستی توسط ادمین برای
    کاربر خطای انسانی کمتری داشته باشد؛ طول ۱۴ کاراکتر آنتروپی کافی
    (~83 بیت) برای یک رمز یک‌بارمصرف که بلافاصله باید عوض شود، تأمین می‌کند.
    """
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))


def hash_token(token: str) -> str:
    """
    SHA256 hash از یک توکن (برای ذخیره refresh token در DB).

    هرگز خودِ توکن را در DB ذخیره نکنید — فقط hash آن را، تا در صورت
    نشت دیتابیس، توکن‌های معتبر لو نروند (مشابه ذخیره پسورد).
    """
    return sha256(token.encode("utf-8")).hexdigest()


# ─── JWT Token ───────────────────────────────────────────────────────────────
def create_access_token(data: dict[str, Any]) -> str:
    """
    Access Token می‌سازد.

    payload حتماً باید شامل:
    - sub: user_id (str)
    - org_id: organization UUID (str)
    - role: نقش کاربر

    نکته: jti (شناسه یکتای توکن) عمداً اضافه می‌شود — بدون آن، دو توکن
    صادرشده برای یک کاربر با claim های یکسان در یک ثانیه (exp با دقت
    ثانیه truncate می‌شود) می‌توانند دقیقاً یکسان دربیایند (مثلاً لاگین و
    بلافاصله تغییر رمز، یا دو تب هم‌زمان) — که برای refresh_token چون
    token_hash در DB باید UNIQUE باشد، منجر به خطای IntegrityError می‌شود.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Refresh Token می‌سازد — بلندمدت‌تر از access token.
    در DB در جدول refresh_tokens ذخیره می‌شود.

    jti یکتا دارد — دلیل در docstring بالا (create_access_token) توضیح
    داده شده؛ برای این توکن حیاتی‌تر است چون token_hash آن UNIQUE در DB است.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Token را decode و اعتبارسنجی می‌کند.
    در صورت نامعتبر بودن UnauthorizedError می‌دهد.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as exc:
        raise UnauthorizedError("توکن نامعتبر یا منقضی شده است") from exc


def decode_access_token(token: str) -> dict[str, Any]:
    """فقط access token می‌پذیرد."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise UnauthorizedError("نوع توکن اشتباه است")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """فقط refresh token می‌پذیرد."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise UnauthorizedError("نوع توکن اشتباه است")
    return payload