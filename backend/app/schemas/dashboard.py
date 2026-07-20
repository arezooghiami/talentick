"""
Talentick — Dashboard Schemas
================================
مدل‌های Pydantic برای endpoint‌های داشبورد Super Admin.

هیچ business logic اینجا نیست — فقط ساختار داده.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Stats ────────────────────────────────────────────────────────────────────

class ContentStats(BaseModel):
    """آمار محتوا به تفکیک نوع."""
    courses: int = Field(0, description="تعداد دوره‌ها")
    podcasts: int = Field(0, description="تعداد پادکست‌ها")
    books: int = Field(0, description="تعداد کتاب‌های صوتی")
    articles: int = Field(0, description="تعداد مقالات")
    total: int = Field(0, description="جمع کل محتواها")


class CompletionStats(BaseModel):
    """آمار تکمیل فعالیت‌ها توسط کاربران."""
    completed_docs: int = Field(0, description="تعداد مدارک تکمیل‌شده — نفر")
    completed_courses: int = Field(0, description="تعداد دوره‌های تکمیل‌شده — نفر")
    completed_quizzes: int = Field(0, description="تعداد آزمون‌های تکمیل‌شده — نفر")


class SuperAdminStats(BaseModel):
    """آمار کلی پلتفرم — خلاصه برای کارت‌های بالای داشبورد."""
    active_users: int = Field(0, description="تعداد کاربران فعال در همه سازمان‌ها")
    total_orgs: int = Field(0, description="تعداد کل سازمان‌ها")
    content: ContentStats = Field(default_factory=ContentStats)
    completion: CompletionStats = Field(default_factory=CompletionStats)
    total_reward_points: int = Field(
        0,
        description="مجموع امتیازهای اهداشده در کل پلتفرم"
    )


# ─── User Growth Chart ────────────────────────────────────────────────────────

class GrowthDataPoint(BaseModel):
    """یک نقطه روی نمودار رشد کاربران."""
    label: str = Field(..., description="برچسب محور X — مثلاً: ۱ فروردین")
    count: int = Field(..., description="تعداد کاربر فعال در آن بازه")


# ─── Top Users ────────────────────────────────────────────────────────────────

class TopUserItem(BaseModel):
    """یک سطر در جدول ۱۰ کاربر برتر."""
    user_id: str
    full_name: str
    role: str
    org_name: str
    quiz_score: int = Field(0, description="مجموع امتیاز آزمون‌ها")


# ─── Recent Tickets ───────────────────────────────────────────────────────────

class RecentTicket(BaseModel):
    """آخرین تیکت‌های پشتیبانی/بازخورد — برای ویجت «آخرین تیکت‌ها» در داشبورد."""
    id: str
    subject: str
    user_name: str
    status: str = Field(description="برچسب فارسی — باز | پاسخ داده‌شده | بسته‌شده")
    rating: int = Field(0, ge=0, le=5, description="۰ یعنی هنوز امتیازدهی نشده")


# ─── Dashboard Response ───────────────────────────────────────────────────────

class SuperAdminDashboardResponse(BaseModel):
    """
    پاسخ کامل endpoint داشبورد Super Admin.

    همه اطلاعات لازم برای render صفحه در یک request.
    """
    stats: SuperAdminStats
    user_growth: list[GrowthDataPoint] = Field(
        default_factory=list,
        description="داده‌های نمودار رشد کاربران — ۱۲ هفته گذشته"
    )
    top_users: list[TopUserItem] = Field(
        default_factory=list,
        description="۱۰ کاربر با بالاترین امتیاز آزمون"
    )
    recent_tickets: list[RecentTicket] = Field(
        default_factory=list,
        description="آخرین تیکت‌های پشتیبانی — V0: placeholder"
    )