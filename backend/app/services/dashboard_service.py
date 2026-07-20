"""
Talentick — Dashboard Service
================================
تمام business logic داشبورد اینجاست.
Router فقط این توابع رو صدا می‌زنه — هیچ query مستقیم در router نیست.

قوانین:
- همه query ها باید async باشن
- super_admin به همه org ها دسترسی دارد — فیلتر org_id لازم نیست
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content
from app.models.organization import Organization
from app.models.quiz import QuizAttempt
from app.models.ticket import Ticket
from app.models.user import User
from app.services import points_service
from app.schemas.dashboard import (
    CompletionStats,
    ContentStats,
    GrowthDataPoint,
    RecentTicket,
    SuperAdminDashboardResponse,
    SuperAdminStats,
    TopUserItem,
)

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    """UTC now با timezone — هیچ وقت naive datetime استفاده نمی‌شه."""
    return datetime.now(timezone.utc)


# ─── Stats ────────────────────────────────────────────────────────────────────

async def _get_stats(db: AsyncSession) -> SuperAdminStats:
    """
    آمار کلی پلتفرم.

    Content و Completion stats از مدل‌های فاز ۲ میان.
    در V0 این مدل‌ها وجود دارن اما ممکنه خالی باشن — مقدار 0 برمی‌گردونیم.
    """

    # ── تعداد کاربران فعال ──
    active_users: int = await db.scalar(
        select(func.count(User.id)).where(User.is_active.is_(True))
    ) or 0

    # ── تعداد سازمان‌های فعال ──
    total_orgs: int = await db.scalar(
        select(func.count(Organization.id)).where(Organization.is_active.is_(True))
    ) or 0

    # ── آمار محتوا ──
    # مدل واقعی Content است (نه ContentModule) — فیلد type (نه content_type).
    # کوئری با try/except محدود به ProgrammingError پوشش داده می‌شود تا اگر
    # migration هنوز روی این جدول اجرا نشده (سناریوی استقرار جزئی)، دیتابورد
    # کرش نکند — اما خطاهای غیرمنتظره‌ی دیگر بی‌صدا قورت داده نمی‌شوند.
    content_stats = ContentStats()
    completion_stats = CompletionStats()

    try:
        type_counts: dict[str, int] = {}
        rows = await db.execute(
            select(Content.type, func.count(Content.id)).group_by(Content.type)
        )
        for content_type, cnt in rows.all():
            type_counts[content_type] = cnt

        content_stats = ContentStats(
            courses=type_counts.get("course", 0),
            podcasts=type_counts.get("podcast", 0),
            books=type_counts.get("book", 0),
            articles=type_counts.get("article", 0),
            total=sum(type_counts.values()),
        )
    except ProgrammingError:
        logger.warning(
            "جدول contents هنوز migrate نشده — آمار محتوا صفر برمی‌گردد.",
            exc_info=True,
        )
        await db.rollback()

    try:
        completed_quizzes: int = await db.scalar(
            select(func.count(QuizAttempt.id)).where(QuizAttempt.passed.is_(True))
        ) or 0
        completion_stats = CompletionStats(
            completed_docs=0,       # فاز ۲: document view tracking
            completed_courses=0,    # فاز ۲: course completion tracking
            completed_quizzes=completed_quizzes,
        )
    except ProgrammingError:
        logger.warning(
            "جدول quiz_attempts هنوز migrate نشده — آمار تکمیل صفر برمی‌گردد.",
            exc_info=True,
        )
        await db.rollback()

    try:
        total_reward_points = await points_service.get_platform_total_points(db)
    except ProgrammingError:
        logger.warning("جدول points_ledger هنوز migrate نشده — کل پاداش صفر برمی‌گردد.", exc_info=True)
        await db.rollback()
        total_reward_points = 0

    return SuperAdminStats(
        active_users=active_users,
        total_orgs=total_orgs,
        content=content_stats,
        completion=completion_stats,
        total_reward_points=total_reward_points,
    )


# ─── User Growth Chart ────────────────────────────────────────────────────────

async def _get_user_growth(db: AsyncSession) -> list[GrowthDataPoint]:
    """
    داده‌های نمودار رشد کاربران — ۱۲ هفته گذشته.

    هر نقطه = تعداد کاربران که در آن هفته ثبت‌نام کرده‌اند.
    برچسب فارسی تولید می‌کنیم — نمایش روی محور X.
    """
    now = _now_utc()
    points: list[GrowthDataPoint] = []

    # نام‌های فارسی روزهای هفته برای label
    # اینجا فقط هفته آخر رو label می‌زنیم
    persian_months = [
        "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
    ]

    for week_back in range(11, -1, -1):  # از ۱۱ هفته پیش تا این هفته
        week_start = now - timedelta(weeks=week_back + 1)
        week_end = now - timedelta(weeks=week_back)

        count: int = await db.scalar(
            select(func.count(User.id)).where(
                User.created_at >= week_start,
                User.created_at < week_end,
            )
        ) or 0

        # label ساده: شماره هفته (در پروژه واقعی تبدیل به تاریخ شمسی)
        label = f"هفته {12 - week_back}"
        points.append(GrowthDataPoint(label=label, count=count))

    return points


# ─── Top Users ────────────────────────────────────────────────────────────────

async def _get_top_users(db: AsyncSession) -> list[TopUserItem]:
    """
    ۱۰ کاربر برتر سامانه بر اساس مجموع امتیاز آزمون.

    اگر QuizAttempt هنوز وجود نداره یا خالیه،
    آخرین کاربران فعال رو برمی‌گردونیم.
    """
    try:
        # join User ↔ Organization ↔ QuizAttempt
        rows = await db.execute(
            select(
                User.id,
                User.full_name,
                User.role,
                Organization.name.label("org_name"),
                func.coalesce(func.sum(QuizAttempt.score), 0).label("total_score"),
            )
            .join(Organization, User.org_id == Organization.id)
            .outerjoin(QuizAttempt, QuizAttempt.user_id == User.id)
            .where(User.is_active.is_(True))
            .group_by(User.id, User.full_name, User.role, Organization.name)
            .order_by(func.coalesce(func.sum(QuizAttempt.score), 0).desc())
            .limit(10)
        )
        return [
            TopUserItem(
                user_id=str(row.id),
                full_name=row.full_name,
                role=row.role,
                org_name=row.org_name,
                quiz_score=int(row.total_score),
            )
            for row in rows.all()
        ]

    except ProgrammingError:
        # جدول quiz_attempts هنوز migrate نشده — fallback: آخرین ۱۰ کاربر فعال
        logger.warning("quiz_attempts در دسترس نیست — fallback به آخرین کاربران فعال.", exc_info=True)
        await db.rollback()
        rows = await db.execute(
            select(User.id, User.full_name, User.role, Organization.name.label("org_name"))
            .join(Organization, User.org_id == Organization.id)
            .where(User.is_active.is_(True))
            .order_by(User.created_at.desc())
            .limit(10)
        )
        return [
            TopUserItem(
                user_id=str(row.id),
                full_name=row.full_name,
                role=row.role,
                org_name=row.org_name,
                quiz_score=0,
            )
            for row in rows.all()
        ]


# ─── Recent Tickets ───────────────────────────────────────────────────────────

_TICKET_STATUS_LABEL_FA = {"open": "باز", "answered": "پاسخ داده‌شده", "closed": "بسته‌شده"}


async def _get_recent_tickets(db: AsyncSession, limit: int = 6) -> list[RecentTicket]:
    """آخرین N تیکت پلتفرم (همه‌ی سازمان‌ها) برای ویجت «آخرین تیکت‌ها»."""
    try:
        rows = await db.execute(
            select(Ticket, User.full_name)
            .join(User, User.id == Ticket.created_by)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
        )
        return [
            RecentTicket(
                id=str(t.id),
                subject=t.subject,
                user_name=user_name,
                status=_TICKET_STATUS_LABEL_FA.get(t.status, t.status),
                rating=t.satisfaction_rating or 0,
            )
            for t, user_name in rows.all()
        ]
    except ProgrammingError:
        logger.warning("جدول tickets هنوز migrate نشده — آخرین تیکت‌ها خالی برمی‌گردد.", exc_info=True)
        await db.rollback()
        return []


# ─── Public API ───────────────────────────────────────────────────────────────

async def get_super_admin_dashboard(db: AsyncSession) -> SuperAdminDashboardResponse:
    """
    تمام داده‌های داشبورد Super Admin را در یک تابع جمع می‌کنه.

    Router فقط این تابع رو صدا می‌زنه.
    هر بخش به صورت مستقل error handle می‌شه — یک بخش fail نکنه کل صفحه خراب بشه.
    """
    stats = await _get_stats(db)
    user_growth = await _get_user_growth(db)
    top_users = await _get_top_users(db)
    recent_tickets = await _get_recent_tickets(db)

    return SuperAdminDashboardResponse(
        stats=stats,
        user_growth=user_growth,
        top_users=top_users,
        recent_tickets=recent_tickets,
    )