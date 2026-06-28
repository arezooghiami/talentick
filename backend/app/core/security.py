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

from datetime import UTC, datetime, timedelta
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


# ─── JWT Token ───────────────────────────────────────────────────────────────
def create_access_token(data: dict[str, Any]) -> str:
    """
    Access Token می‌سازد.

    payload حتماً باید شامل:
    - sub: user_id (str)
    - org_id: organization UUID (str)
    - role: نقش کاربر
    """
    payload = data.copy()
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Refresh Token می‌سازد — بلندمدت‌تر از access token.
    در DB در جدول refresh_tokens ذخیره می‌شود.
    """
    payload = data.copy()
    expire = datetime.now(UTC) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload.update({"exp": expire, "type": "refresh"})
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