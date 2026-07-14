"""
Talentick — Dependencies & RBAC Guards
========================================
تمام Dependency های FastAPI اینجاست.

معماری:
- get_current_user  → پایه — JWT decode + user از DB
- require_active    → کاربر باید is_active=True باشد
- require_super_admin → فقط super_admin
- require_org_admin  → org_admin یا بالاتر
- require_manager    → manager یا بالاتر
- require_same_org   → کاربر فقط به org خودش دسترسی داره

قانون طلایی: هر endpoint باید حداقل یک guard داشته باشد.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User

# ─── OAuth2 Scheme ────────────────────────────────────────────────────────────
# tokenUrl باید با endpoint لاگین match کنه
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# مسیرهایی که حتی اگر must_change_password=True باشد، همچنان مجازند —
# باید حداقل «تغییر رمز» و «مشاهده پروفایل خود» و «خروج» در دسترس بمانند
# تا کاربر بتواند خودش را از این وضعیت خارج کند.
_PASSWORD_CHANGE_EXEMPT_PATHS = {
    "/api/auth/change-password",
    "/api/auth/me",
    "/api/auth/logout",
}

# ─── Role Hierarchy ───────────────────────────────────────────────────────────
# هر نقش شامل تمام نقش‌های پایین‌تر از خودشه
ROLE_HIERARCHY: dict[str, int] = {
    "super_admin": 100,
    "org_admin": 50,
    "manager": 30,
    "employee": 10,
}


def _role_level(role: str) -> int:
    """سطح عددی یک نقش — نقش ناشناخته = ۰."""
    return ROLE_HIERARCHY.get(role, 0)


# ─── Base Dependency ──────────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT را decode می‌کند و User را از دیتابیس برمی‌گرداند.

    همچنین قفل must_change_password اینجا (پایین‌ترین/مشترک‌ترین
    dependency که همه‌ی guard ها و CurrentUser از آن مشتق می‌شوند) اعمال
    می‌شود تا هیچ endpointی (فعلی یا آینده) نتواند این بررسی را فراموش
    کند — مگر مسیرهای صراحتاً معاف‌شده در _PASSWORD_CHANGE_EXEMPT_PATHS.

    خطاها:
    - 401: token نامعتبر یا منقضی
    - 401: کاربر در دیتابیس وجود ندارد
    - 428: رمز عبور توسط ادمین تنظیم شده و کاربر هنوز آن را عوض نکرده
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اعتبارسنجی ناموفق — لطفاً دوباره وارد شوید",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exc

    user_id_raw: str | None = payload.get("sub")
    if not user_id_raw:
        raise credentials_exc

    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exc

    if user.must_change_password and request.url.path not in _PASSWORD_CHANGE_EXEMPT_PATHS:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="رمز عبور شما توسط مدیر سیستم تنظیم شده — قبل از ادامه باید آن را تغییر دهید",
        )

    return user


# ─── Active Guard ─────────────────────────────────────────────────────────────

async def require_active(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    کاربر باید فعال باشد.

    حتی اگر token معتبر باشد، کاربر غیرفعال‌شده نمی‌تواند وارد شود.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری غیرفعال است — با مدیر سیستم تماس بگیرید",
        )
    return current_user


# ─── Role Guards ──────────────────────────────────────────────────────────────

def _require_role(minimum_role: str):
    """
    Factory تابع: یک guard می‌سازه که حداقل نقش رو بررسی می‌کنه.

    مثال:
        require_manager = _require_role("manager")
        → manager, org_admin, super_admin مجاز هستند
        → employee مجاز نیست
    """
    async def guard(
        current_user: Annotated[User, Depends(require_active)],
    ) -> User:
        if _role_level(current_user.role) < _role_level(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"دسترسی محدود است — نقش مورد نیاز: {minimum_role}",
            )
        return current_user

    # نام تابع رو set می‌کنیم تا Swagger زیبا بشه
    guard.__name__ = f"require_{minimum_role}"
    return guard


# ─── Exported Guards ──────────────────────────────────────────────────────────
# این‌ها مستقیماً در Router ها استفاده می‌شن

require_super_admin = _require_role("super_admin")
"""فقط super_admin — برای endpoint های پلتفرم."""

require_org_admin = _require_role("org_admin")
"""org_admin و بالاتر — برای مدیریت سازمان."""

require_manager = _require_role("manager")
"""manager و بالاتر — برای گزارش‌های تیم."""

require_employee = _require_role("employee")
"""هر کاربر فعال — برای endpoint های عمومی."""


# ─── Annotated Type Aliases ───────────────────────────────────────────────────
# برای استفاده راحت‌تر در Router ها با نحو Annotated:
#
#   async def my_endpoint(user: CurrentUser): ...
#   async def admin_endpoint(user: SuperAdmin): ...
#
# این alias ها با روش قدیمی Depends() هم سازگار هستند.

CurrentUser = Annotated[User, Depends(get_current_user)]
"""کاربر لاگین‌شده — هر نقشی."""

ActiveUser = Annotated[User, Depends(require_active)]
"""کاربر فعال — is_active=True."""

SuperAdmin = Annotated[User, Depends(require_super_admin)]
"""فقط super_admin."""

OrgAdmin = Annotated[User, Depends(require_org_admin)]
"""org_admin و بالاتر."""

Manager = Annotated[User, Depends(require_manager)]
"""manager و بالاتر."""

Employee = Annotated[User, Depends(require_employee)]
"""هر کاربر فعال."""


# ─── Org Isolation Guard ──────────────────────────────────────────────────────

class OrgIsolation:
    """
    Dependency که تضمین می‌کند کاربر فقط به org خودش دسترسی داره.

    super_admin از این قانون مستثنی است — به همه org ها دسترسی دارد.

    استفاده:
        @router.get("/orgs/{org_id}/users")
        async def list_users(
            org_id: uuid.UUID,
            _: None = Depends(OrgIsolation(org_id)),
            ...
        )

    توجه: چون path parameter مستقیم به __init__ قابل پاس نیست،
    این guard رو در بدنه endpoint با متد check() صدا بزنید.
    """

    @staticmethod
    async def check(
        target_org_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """
        بررسی می‌کنه کاربر به org مورد نظر دسترسی داره.

        در Router:
            await OrgIsolation.check(org_id, current_user)
        """
        if current_user.role == "super_admin":
            return  # super_admin به همه org ها دسترسی دارد

        if current_user.org_id != target_org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="دسترسی به این سازمان مجاز نیست",
            )


# ─── Shared Org-Scope Helper ───────────────────────────────────────────────────
# پیش‌تر این منطق در users.py / content.py / departments.py / positions.py
# عیناً چهار بار کپی‌پیست شده بود — نسخه‌ی واحد اینجا تا هیچ router جدیدی
# این بررسی حیاتی Tenant Isolation را فراموش نکند یا نسخه‌ی ناهماهنگ از آن
# ننویسد.

def enforce_org_scope(current_user: User, target_org_id: uuid.UUID) -> None:
    """
    بررسی می‌کند کاربر به سازمانِ target_org_id دسترسی دارد.

    super_admin از این قانون مستثناست (به همه‌ی سازمان‌ها دسترسی دارد).
    سایر نقش‌ها فقط به سازمان خودشان — در غیر این صورت 403.

    استفاده در Router (بعد از fetch رکورد و پیش از بازگرداندن آن):
        enforce_org_scope(current_user, resource.org_id)
    """
    if current_user.role == "super_admin":
        return
    if str(current_user.org_id) != str(target_org_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی به این سازمان مجاز نیست",
        )