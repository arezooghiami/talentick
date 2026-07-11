"""
Talentick — Rate Limiter (In-Memory)
=======================================
محدودکننده ساده‌ی نرخ درخواست برای endpoint های حساس (مثل login) —
برای جلوگیری از حملات Brute Force روی پسورد.

⚠️ محدودیت این پیاده‌سازی:
    حافظه در سطح یک پروسه (process) نگه‌داری می‌شود. اگر برنامه با چند
    worker/instance اجرا شود (که در production معمول است)، هر پروسه
    شمارنده‌ی جدا دارد. برای production واقعی با چند worker/replica،
    این باید با Redis (یا میان‌افزاری مثل slowapi + redis) جایگزین شود.
    برای V0 (یک instance) این سطح از محافظت کافی و بهتر از هیچ است.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """محدودکننده‌ی «حداکثر N درخواست در هر پنجره‌ی زمانی» بر اساس یک کلید دلخواه."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        """
        در صورت عبور از حد مجاز، HTTP 429 raise می‌کند.
        در غیر این صورت، تلاش فعلی را ثبت می‌کند.
        """
        now = time.monotonic()
        hits = self._hits[key]

        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_attempts:
            retry_after = max(1, int(self.window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"تعداد تلاش‌های شما بیش از حد مجاز است — {retry_after} ثانیه دیگر دوباره امتحان کنید",
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)

    def reset(self, key: str) -> None:
        """پس از موفقیت (مثلاً ورود صحیح) شمارنده را پاک می‌کند."""
        self._hits.pop(key, None)


# ─── نمونه‌ی مشترک برای Login — حداکثر ۵ تلاش در هر ۵ دقیقه به ازای هر کلید ────
login_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=300)
