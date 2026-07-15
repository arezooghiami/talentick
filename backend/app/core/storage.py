"""
Talentick — Storage Utilities (MinIO)
=======================================
آپلود فایل/تصویر/ویدیو محتوا به MinIO (سازگار با S3).

استفاده:
    from app.core.storage import upload_file
    url = await upload_file(file, org_id, subfolder="contents")
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import timedelta
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


@lru_cache
def get_minio_client() -> Minio:
    """Client سینگلتون MinIO — یک بار ساخته می‌شود."""
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_use_ssl,
    )


def _public_read_policy(bucket_name: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
        }],
    })


@lru_cache
def ensure_bucket() -> None:
    """
    در صورت نبودن bucket، آن را می‌سازد؛ در هر دو حالت (جدید/موجود) سیاست
    public-read روی آبجکت‌ها را اعمال می‌کند.

    نکته: قبلاً این تابع فقط bucket را می‌ساخت و هیچ policy‌ای تنظیم
    نمی‌کرد — در نتیجه آبجکت‌های آپلودشده با «Access Denied» مواجه
    می‌شدند چون MinIO به‌صورت پیش‌فرض bucket را private می‌سازد.
    با lru_cache این تابع فقط یک‌بار در طول عمر پروسه اجرا می‌شود.
    """
    client = get_minio_client()
    if not client.bucket_exists(settings.minio_bucket_name):
        client.make_bucket(settings.minio_bucket_name)
    client.set_bucket_policy(settings.minio_bucket_name, _public_read_policy(settings.minio_bucket_name))


def _public_url(object_name: str) -> str:
    scheme = "https" if settings.minio_use_ssl else "http"
    return f"{scheme}://{settings.minio_endpoint}/{settings.minio_bucket_name}/{object_name}"


async def upload_file(file: UploadFile, org_id: uuid.UUID, subfolder: str = "contents") -> dict:
    """
    فایل آپلودی را در MinIO ذخیره می‌کند — مسیر جداگانه به ازای هر سازمان.

    خروجی: {"url": ..., "filename": ..., "size": ..., "content_type": ...}
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
        "url": _public_url(object_name),
        "filename": file.filename,
        "size": len(data),
        "content_type": file.content_type,
    }


def presigned_url(object_path: str, expires_minutes: int = 60) -> str:
    """
    آدرس موقت امضاشده برای دسترسی به فایل private (در صورت نیاز در آینده).
    در V0 از bucket عمومی استفاده می‌شود و این تابع استفاده نمی‌شود.
    """
    client = get_minio_client()
    return client.presigned_get_object(
        settings.minio_bucket_name, object_path, expires=timedelta(minutes=expires_minutes)
    )
