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

استفاده (آپلود قدیمی — چندبخشی از طریق اپ، هنوز برای فایل‌های کوچک/غیرویدیویی
استفاده می‌شود):
    from app.core.storage import upload_file
    result = await upload_file(file, org_id, subfolder="contents")
    # result["url"] == "/api/files/<org_id>/contents/<uuid>.<ext>"

استفاده (presigned — برای فایل حجیم/ویدیو؛ نگاه کنید به routers/content.py):
    از create_upload_url مرورگر مستقیم و بدون واسطه‌ی اپ به MinIO آپلود
    می‌کند (بدون بافر کردن کل فایل در RAM اپ) و از create_download_url یک
    presigned GET کوتاه‌مدت برای پخش/دانلود مستقیم (با پشتیبانی بومی از
    Range request برای seek سریع ویدیو) می‌سازد.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from datetime import timedelta
from functools import lru_cache

from fastapi import HTTPException, Request, UploadFile, status
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

# سقف حجم فقط برای مسیر آپلود قدیمی (چندبخشی از طریق اپ) به‌عنوان محافظ حافظه
# اپلیکیشن معنا دارد — نگاه کنید به تابع upload_file. مسیر presigned
# (create_upload_url) اصلاً از این محدودیت عبور نمی‌کند چون بایت‌های فایل هرگز
# از اپ رد نمی‌شوند؛ کاربردش الان فقط به‌عنوان مقدار پیش‌فرض سقف مخصوص
# document_type در آنبوردینگ کارمند باقی مانده (services/employee_onboarding_service.py).
MAX_FILE_SIZE_MB = 200

# اعتبار presigned URL — هم برای PUT آپلود (باید کل مدت آپلود فایل حجیم را
# پوشش دهد) و هم برای GET پخش (باید یک جلسه‌ی تماشای طولانی را پوشش دهد).
PRESIGNED_URL_EXPIRY = timedelta(hours=6)

FILES_URL_PREFIX = "/api/files/"

# پیشوند مسیر برای فایل‌های Public/General (متعلق به هیچ سازمانی نیست) —
# مثل کاور/عکس گالری‌ی Public که super_admin بدون انتخاب سازمان می‌سازد.
# routers/files.py این پیشوند را تشخیص می‌دهد و enforce_org_scope را برای
# آن اجرا نمی‌کند (هر کاربر احراز هویت‌شده می‌تواند این فایل‌ها را ببیند).
PUBLIC_PATH_SEGMENT = "public"


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


def build_object_name(filename: str | None, org_id: uuid.UUID | None, subfolder: str) -> str:
    """پسوند را اعتبارسنجی و یک object_name یکتا می‌سازد — هم مسیر آپلود قدیمی
    (upload_file) و هم مسیر presigned (create_upload_url) از این استفاده می‌کنند."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"فرمت فایل مجاز نیست. فرمت‌های مجاز: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    org_segment = str(org_id) if org_id is not None else PUBLIC_PATH_SEGMENT
    return f"{org_segment}/{subfolder}/{uuid.uuid4()}.{ext}"


def get_public_minio_client(request: Request) -> Minio:
    """
    Client مخصوص presigned URL. بر خلاف get_minio_client (که به `minio:9000`
    داخل شبکه‌ی docker وصل می‌شود و از بیرون هرگز resolve نمی‌شود)، این یکی
    همان host/scheme درخواست واقعی مرورگر را به‌عنوان endpoint می‌گیرد — چون
    nginx یک location برای پراکسی مستقیم به MinIO دارد (نگاه کنید به
    nginx/nginx.conf، location به نام bucket)، presigned URL ساخته‌شده با این
    host از طریق همان مسیر برای مرورگر در دسترس خواهد بود.
    """
    host = request.headers.get("host") or request.url.netloc
    forwarded_proto = request.headers.get("x-forwarded-proto")
    secure = (forwarded_proto or request.url.scheme) == "https"
    return Minio(
        host,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=secure,
    )


async def create_upload_url(request: Request, filename: str | None, org_id: uuid.UUID | None, subfolder: str = "contents") -> dict:
    """
    presigned PUT URL برای آپلود مستقیم مرورگر → MinIO — بدون عبور بایت‌های
    فایل از حافظه‌ی اپ. برای ویدیوهای چند ساعته/چند گیگابایتی دوره‌ها ضروری
    است (خواندن کامل چنین فایلی در RAM اپ نه عملی است نه امن).

    خروجی: {"upload_url": presigned PUT، "url": مسیر پایدار داخلی برای ذخیره
    در دیتابیس بعد از تکمیل آپلود، "object_name": ...}
    """
    object_name = build_object_name(filename, org_id, subfolder)
    ensure_bucket()
    client = get_public_minio_client(request)
    upload_url = await asyncio.to_thread(
        client.presigned_put_object,
        settings.minio_bucket_name,
        object_name,
        expires=PRESIGNED_URL_EXPIRY,
    )
    return {
        "upload_url": upload_url,
        "url": f"{FILES_URL_PREFIX}{object_name}",
        "object_name": object_name,
    }


async def create_download_url(request: Request, object_name: str) -> str:
    """presigned GET کوتاه‌مدت — MinIO خودش Range request (seek ویدیو) را بومی هندل می‌کند."""
    client = get_public_minio_client(request)
    return await asyncio.to_thread(
        client.presigned_get_object,
        settings.minio_bucket_name,
        object_name,
        expires=PRESIGNED_URL_EXPIRY,
    )


async def upload_file(file: UploadFile, org_id: uuid.UUID | None, subfolder: str = "contents") -> dict:
    """
    فایل آپلودی را در MinIO (private) ذخیره می‌کند — مسیر جداگانه به ازای هر سازمان.

    org_id=None یعنی فایل Public/General است (متعلق به هیچ سازمانی نیست —
    مثل کاور یک گالری Public) و به‌جای UUID سازمان، از PUBLIC_PATH_SEGMENT
    استفاده می‌شود؛ routers/files.py دسترسی به آن را برای هر کاربر
    احراز هویت‌شده مجاز می‌کند.

    خروجی: {"url": "/api/files/<object_name>", "filename": ..., "size": ..., "content_type": ...}
    مقدار "url" داخلی و پایدار است (هرگز منقضی نمی‌شود) — نه یک presigned URL.
    """
    object_name = build_object_name(file.filename, org_id, subfolder)
    data = await file.read()

    try:
        ensure_bucket()
        client = get_minio_client()
        # put_object در minio-py synchronous/blocking است — بدون to_thread حین
        # آپلود فایل حجیم کل event loop قفل می‌شود و هیچ درخواست هم‌زمان دیگری
        # (آپلود/دانلود کاربران دیگر) پاسخ داده نمی‌شود.
        await asyncio.to_thread(
            client.put_object,
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
