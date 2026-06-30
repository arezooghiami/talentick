"""
Talentick — Dashboard Router
================================
GET /api/dashboard/super-admin → آمار و داده‌های داشبورد Super Admin

قوانین:
- فقط super_admin دسترسی دارد — guard: require_super_admin
- هیچ business logic اینجا نیست — همه چیز در dashboard_service
- response_model صریح تعریف شده تا Swagger دقیق باشه
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_super_admin
from app.models.user import User
from app.schemas.dashboard import SuperAdminDashboardResponse
from app.services import dashboard_service

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "/super-admin",
    response_model=SuperAdminDashboardResponse,
    summary="داشبورد Super Admin",
    description="""
    تمام آمار و داده‌های لازم برای صفحه داشبورد Super Admin.

    **دسترسی:** فقط کاربران با نقش `super_admin`

    **شامل:**
    - آمار کلی: کاربران فعال، سازمان‌ها، محتوا، آزمون
    - نمودار رشد کاربران — ۱۲ هفته گذشته
    - ۱۰ کاربر برتر سامانه
    - آخرین تیکت‌های پشتیبانی (V0: placeholder)
    """,
)
async def get_super_admin_dashboard(
    _current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> SuperAdminDashboardResponse:
    """
    داشبورد Super Admin — داده‌های کامل در یک request.

    `_current_user` فقط برای اعمال guard است — در بدنه تابع استفاده نمی‌شه.
    """
    return await dashboard_service.get_super_admin_dashboard(db)