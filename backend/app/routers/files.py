"""
Talentick — Files Router (Authenticated MinIO Proxy)
========================================================
باکت MinIO از نوع private است — این router تنها راه دسترسی به فایل‌های
آپلودشده (کاور/سند/ویدیو/آواتار/لوگو و ...) است. هیچ URL مستقیم عمومی
MinIO دیگر برنمی‌گردد (core/storage.py:upload_file).

Routes:
    GET /api/files/playback-url/{object_path} → لینک presigned کوتاه‌مدت
    (بعد از احراز هویت + بررسی org isolation) برای پخش/دانلود مستقیم از
    MinIO — MinIO خودش Range request (seek ویدیو) را بومی هندل می‌کند،
    برخلاف مسیر پایین که کل فایل را از اپ عبور می‌دهد. باید همیشه *قبل*
    از مسیر عمومی زیر ثبت شود چون هر دو روی همان prefix path-converter
    دارند.

    GET /api/files/{object_path} → استریم فایل از MinIO، فقط بعد از
    احراز هویت (ActiveUser) و بررسی org isolation — اولین بخش مسیر همیشه
    org_id صاحب فایل است (نگاه کنید به core/storage.py:upload_file).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from minio.error import S3Error

from app.config import settings
from app.core.storage import PUBLIC_PATH_SEGMENT, create_download_url, get_minio_client, object_org_id
from app.dependencies import ActiveUser, enforce_org_scope

router = APIRouter(prefix="/api/files", tags=["Files"])


def _check_file_access(object_path: str, current_user) -> None:
    """احراز org isolation برای یک object_path — هر دو route زیر از این استفاده می‌کنند."""
    raw_org_id = object_org_id(object_path)

    # فایل Public/General (بدون سازمان — نگاه کنید به core/storage.py:upload_file)
    # برای هر کاربر احراز هویت‌شده قابل مشاهده است، بدون بررسی org isolation.
    if raw_org_id == PUBLIC_PATH_SEGMENT:
        return

    try:
        org_id = uuid.UUID(raw_org_id) if raw_org_id else None
    except ValueError:
        org_id = None

    if org_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل یافت نشد")

    enforce_org_scope(current_user, org_id)


@router.get("/playback-url/{object_path:path}", summary="لینک موقت presigned برای پخش/دانلود مستقیم از MinIO")
async def get_file_playback_url(object_path: str, request: Request, current_user: ActiveUser) -> dict:
    _check_file_access(object_path, current_user)

    client = get_minio_client()
    try:
        client.stat_object(settings.minio_bucket_name, object_path)
    except S3Error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل یافت نشد")

    return {"url": await create_download_url(request, object_path)}


@router.get("/{object_path:path}", summary="دریافت فایل آپلودشده (کاور/سند/ویدیو/آواتار/لوگو و ...)")
async def get_file(object_path: str, current_user: ActiveUser) -> StreamingResponse:
    _check_file_access(object_path, current_user)

    client = get_minio_client()
    try:
        stat = client.stat_object(settings.minio_bucket_name, object_path)
    except S3Error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل یافت نشد")

    def _stream():
        response = client.get_object(settings.minio_bucket_name, object_path)
        try:
            for chunk in response.stream(64 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return StreamingResponse(
        _stream(),
        media_type=stat.content_type or "application/octet-stream",
        headers={"Content-Length": str(stat.size)},
    )
