"""
Talentick — اصلاح مسیر فایل‌های محتوا (Migration یک‌باره)
===============================================================
باگ: routers/content.py:/upload قبلاً همیشه فایل را زیر پوشه‌ی سازمانِ
کاربر آپلودکننده (super_admin) ذخیره می‌کرد، نه سازمانی که واقعاً برای
محتوا انتخاب شده بود (content.org_id / is_public). نتیجه: کاربر همان
سازمانِ محتوا موقع دانلود از routers/files.py با 403 «دسترسی به این
سازمان مجاز نیست» مواجه می‌شد، چون org isolation آنجا فقط بر اساس
segment اول مسیر فایل چک می‌شود، نه org_id واقعی رکورد محتوا.

این اسکریپت تمام Content/ContentItem موجود را می‌گردد، مسیر واقعی هر
فایل (thumbnail_url / instructor_avatar_url / media_url) را با
org_id واقعی محتوا مقایسه می‌کند و در صورت ناهم‌خوانی:
  1. فایل را در MinIO به مسیر صحیح کپی می‌کند (copy_object)
  2. کپی را با stat_object تأیید می‌کند
  3. فایل قدیمی را حذف می‌کند (remove_object)
  4. مقدار URL را در دیتابیس به‌روزرسانی می‌کند

اجرا (پیش‌فرض: فقط گزارش، بدون تغییر واقعی):
    python fix_media_org_paths.py

اعمال واقعی تغییرات:
    python fix_media_org_paths.py --apply

⚠️ باید داخل همان محیطی اجرا شود که به DB و MinIO واقعی (production)
دسترسی دارد — مثلاً:
    docker compose -f docker-compose.yml -f docker-compose.prod.yml \
        exec app python fix_media_org_paths.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select  # noqa: E402

from app.core.storage import (  # noqa: E402
    FILES_URL_PREFIX,
    PUBLIC_PATH_SEGMENT,
    get_minio_client,
)
from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.content import Content, ContentItem  # noqa: E402


def expected_org_segment(org_id) -> str:
    return str(org_id) if org_id is not None else PUBLIC_PATH_SEGMENT


def planned_object_name(url: str | None, expected_segment: str) -> str | None:
    """اگر url یک مسیر داخلی (/api/files/...) با org segment نادرست باشد،
    object_name جدید را برمی‌گرداند؛ در غیر این صورت None (نیازی به تغییر نیست
    یا اصلاً مسیر داخلی نیست — مثل لینک خارجی در آیتم‌های type=link)."""
    if not url or not url.startswith(FILES_URL_PREFIX):
        return None
    object_name = url[len(FILES_URL_PREFIX):]
    if "/" not in object_name:
        return None
    current_segment, rest = object_name.split("/", 1)
    if current_segment == expected_segment:
        return None
    return f"{expected_segment}/{rest}"


def move_object(client, src: str, dst: str) -> None:
    from minio.commonconfig import CopySource

    client.copy_object(settings.minio_bucket_name, dst, CopySource(settings.minio_bucket_name, src))
    client.stat_object(settings.minio_bucket_name, dst)  # تأیید موفقیت کپی قبل از حذف مبدا
    client.remove_object(settings.minio_bucket_name, src)


async def run(apply: bool) -> None:
    client = get_minio_client() if apply else None
    planned = 0
    failed = 0

    async with AsyncSessionLocal() as db:
        contents = (await db.execute(select(Content))).scalars().all()

        for content in contents:
            expected = expected_org_segment(content.org_id)

            for field in ("thumbnail_url", "instructor_avatar_url"):
                url = getattr(content, field)
                new_object = planned_object_name(url, expected)
                if new_object is None:
                    continue
                old_object = url[len(FILES_URL_PREFIX):]
                print(f"[content {content.id}] {field}:\n    {old_object}\n -> {new_object}")
                planned += 1
                if apply:
                    try:
                        move_object(client, old_object, new_object)
                        setattr(content, field, FILES_URL_PREFIX + new_object)
                    except Exception as e:  # noqa: BLE001
                        failed += 1
                        print(f"    ❌ خطا: {e}")

            items = (
                await db.execute(select(ContentItem).where(ContentItem.content_id == content.id))
            ).scalars().all()
            for item in items:
                new_object = planned_object_name(item.media_url, expected)
                if new_object is None:
                    continue
                old_object = item.media_url[len(FILES_URL_PREFIX):]
                print(f"[item {item.id}] media_url:\n    {old_object}\n -> {new_object}")
                planned += 1
                if apply:
                    try:
                        move_object(client, old_object, new_object)
                        item.media_url = FILES_URL_PREFIX + new_object
                    except Exception as e:  # noqa: BLE001
                        failed += 1
                        print(f"    ❌ خطا: {e}")

        if apply and planned:
            await db.commit()

    print()
    if not planned:
        print("✅ هیچ فایلی نیاز به جابه‌جایی نداشت.")
    elif apply:
        print(f"✅ اعمال شد: {planned - failed} فایل جابه‌جا شد، {failed} خطا.")
    else:
        print(f"ℹ️ حالت dry-run — {planned} فایل نیاز به جابه‌جایی دارند. برای اعمال واقعی با --apply اجرا کنید.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="تغییرات را واقعاً اعمال کن (وگرنه فقط گزارش می‌دهد)")
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply))
