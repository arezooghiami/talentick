"""
Talentick — Storage Utilities (MinIO)
=======================================
آپلود فایل/تصویر/ویدیو محتوا به MinIO (سازگار با S3) + سرو امن آن‌ها.

معماری امنیتی:
    باکت MinIO **private** است (بدون هیچ policy عمومی). upload_file دیگر
    URL مستقیم MinIO را برنمی‌گرداند، بلکه یک مسیر پایدار داخلی برمی‌گرداند:
        /api/files/{object_name}
    که توسط routers/files.py سرو می‌شود — آن endpoint احراز هویت + org
    isolation را چک می‌کند و بایت‌های فایل را مستقیماً از MinIO stream
    می‌کند (بدون افشای هرگز یک presigned URL به مرورگر، که چون هاست
    داخلی docker یعنی `minio:9000` است، از بیرون هم قابل resolve نبود).

    این مقدار (`/api/files/...`) همان چیزی است که در دیتابیس
    (content.media_url، documents.file_url، announcements.media_url و...)
    ذخیره می‌شود — چون هرگز منقضی نمی‌شود (برخلاف presigned URL که اگر
    داخل دیتابیس ذخیره شود، بعد از انقضا دیگر کار نمی‌کند).

استفاده:
    from app.core.storage import upload_file
    result = await upload_file(file, org_id, subfolder="contents")
    # result["url"] == "/api/files/<org_id>/contents/<uuid>.<ext>"
"""

from __future__ import annotations

import io
import uuid
from functools import lru_cache

from fastapi import HTTPException, UploadFile, status
from minio import Minio
from minio.error import S3Error

from app.config import settings

# پسوندهای مجاز برای آپلود محتوا — جلوگیری از آپلود فایل اجرایی/خطرناک
# نکته امنیتی: svg عمداً در این لیست نیست — فایل SVG می‌تواند حاوی
# <script>/onload> باشد و در صورت نمایش inline در مرورگر منجر به
# Stored XSS شود؛ برای آیکون/وکتور از فرمت‌های امن (png/webp) استفاده شود.
ALLOWED_EXTENSIONS = {
    # تصویر
    "jpg", "jpeg", "png", "webp", "gif",
    # ویدیو
    "mp4", "webm", "mov",
    # صوت (پادکست)
    "mp3", "wav", "m4a", "ogg",
    # سند
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx",
}

MAX_FILE_SIZE_MB = 200

FILES_URL_PREFIX = "/api/files/"


@lru_cache
def get_minio_client() -> Minio:
    """Client سینگلتون MinIO — یک بار ساخته می‌شود."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_use_ssl,
    )


@lru_cache
def ensure_bucket() -> None:
    """
    در صورت نبودن bucket، آن را می‌سازد و هر policy عمومی قبلی را (اگر از
    نسخه‌های قدیمی‌تر باقی مانده باشد) صراحتاً حذف می‌کند تا باکت private
    بماند — صرفاً «هیچ policy جدیدی تنظیم نکردن» کافی نیست، چون اگر این
    باکت قبلاً توسط نسخه‌ی قدیمی این تابع public-read شده باشد، آن policy
    در سمت سرور MinIO باقی می‌ماند تا صراحتاً پاک شود.

    دسترسی به فایل‌ها فقط از طریق routers/files.py (احراز هویت‌شده،
    org-scoped) ممکن است، نه با URL مستقیم عمومی.
    """
    client = get_minio_client()
    if not client.bucket_exists(settings.minio_bucket_name):
        client.make_bucket(settings.minio_bucket_name)
        return

    try:
        client.delete_bucket_policy(settings.minio_bucket_name)
    except S3Error:
        pass  # از قبل policy‌ای وجود نداشت


async def upload_file(file: UploadFile, org_id: uuid.UUID, subfolder: str = "contents") -> dict:
    """
    فایل آپلودی را در MinIO (private) ذخیره می‌کند — مسیر جداگانه به ازای هر سازمان.

    خروجی: {"url": "/api/files/<object_name>", "filename": ..., "size": ..., "content_type": ...}
    مقدار "url" داخلی و پایدار است (هرگز منقضی نمی‌شود) — نه یک presigned URL.
    """
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"فرمت فایل مجاز نیست. فرمت‌های مجاز: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"حجم فایل بیش از حد مجاز است (حداکثر {MAX_FILE_SIZE_MB}MB)",
        )

    object_name = f"{org_id}/{subfolder}/{uuid.uuid4()}.{ext}"

    try:
        ensure_bucket()
        client = get_minio_client()
        client.put_object(
            settings.minio_bucket_name,
            object_name,
            data=io.BytesIO(data),
            length=len(data),
            content_type=file.content_type or "application/octet-stream",
        )
    except S3Error as e:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"خطا در آپلود فایل به فضای ذخیره‌سازی: {e}",
        )

    return {
        "url": f"{FILES_URL_PREFIX}{object_name}",
        "filename": file.filename,
        "size": len(data),
        "content_type": file.content_type,
    }


def object_org_id(object_name: str) -> str | None:
    """اولین بخش object_name (قبل از اولین «/») همیشه org_id است — نگاه کنید به upload_file."""
    return object_name.split("/", 1)[0] if "/" in object_name else None
