"""
Talentick — Custom Exceptions
================================
خطاهای HTTP استاندارد با پیام‌های فارسی.

استفاده:
    from app.core.exceptions import NotFoundError, ForbiddenError
    raise NotFoundError("محتوا یافت نشد")
"""

from fastapi import HTTPException, status


class BadRequestError(HTTPException):
    """400 — درخواست نامعتبر."""

    def __init__(self, detail: str = "درخواست نامعتبر است"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedError(HTTPException):
    """401 — احراز هویت لازم است."""

    def __init__(self, detail: str = "لطفاً وارد شوید"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    """403 — دسترسی ندارید."""

    def __init__(self, detail: str = "دسترسی غیرمجاز"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(HTTPException):
    """404 — یافت نشد."""

    def __init__(self, detail: str = "مورد درخواستی یافت نشد"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(HTTPException):
    """409 — تکراری است."""

    def __init__(self, detail: str = "این مورد قبلاً ثبت شده است"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnprocessableError(HTTPException):
    """422 — داده قابل پردازش نیست."""

    def __init__(self, detail: str = "داده‌های ارسالی قابل پردازش نیستند"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )


class InternalError(HTTPException):
    """500 — خطای سرور."""

    def __init__(self, detail: str = "خطای داخلی سرور"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )