"""Object storage backend (MinIO / S3-compatible) for media uploads.

Replaces local-disk storage under uploads/<tenant>/ so uploaded files
survive a container redeploy. The public URL contract is unchanged —
callers still get back /media/<tenant>/<object-name> — only what's behind
that URL changed, from a StaticFiles mount to a streaming proxy in
app/routers/media.py.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO, Iterator

from minio import Minio
from minio.error import S3Error

from app.config import settings

_client: Minio | None = None
_bucket_ready = False


def client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def _ensure_bucket() -> None:
    global _bucket_ready
    if _bucket_ready:
        return
    c = client()
    try:
        if not c.bucket_exists(settings.minio_bucket):
            c.make_bucket(settings.minio_bucket)
    except S3Error as e:
        raise RuntimeError(f"Could not reach object storage: {e}") from e
    _bucket_ready = True


class UploadTooLarge(Exception):
    pass


def put_object(tenant_slug: str, filename: str, stream: BinaryIO, content_type: str) -> tuple[str, int]:
    """Stream-upload a file, enforcing the configured size limit as bytes
    arrive (rather than buffering the whole upload in memory first)."""
    _ensure_bucket()
    ext = Path(filename or "").suffix.lower()
    object_name = f"{tenant_slug}/{uuid.uuid4().hex}{ext}"
    limit = settings.max_upload_mb * 1024 * 1024

    def _bounded_chunks() -> Iterator[bytes]:
        seen = 0
        while chunk := stream.read(1024 * 1024):
            seen += len(chunk)
            if seen > limit:
                raise UploadTooLarge(f"File exceeds {settings.max_upload_mb} MB limit")
            yield chunk

    # minio-py needs a real file-like object (for length/seek), not a
    # generator, so buffer through a bounded read wrapper instead of
    # collecting all chunks in memory. put_object requires a known length
    # OR chunked upload via a stream; using a spooled temp file keeps
    # memory bounded for typical lesson media (tens/hundreds of MB) while
    # avoiding a second local-disk-forever code path.
    import tempfile
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as tmp:
        size = 0
        try:
            for chunk in _bounded_chunks():
                tmp.write(chunk)
                size += len(chunk)
        except UploadTooLarge:
            raise
        tmp.seek(0)
        client().put_object(
            settings.minio_bucket, object_name, tmp, length=size,
            content_type=content_type or "application/octet-stream",
        )
    return object_name, size


def stat_object(object_name: str):
    _ensure_bucket()
    try:
        return client().stat_object(settings.minio_bucket, object_name)
    except S3Error:
        return None


def get_object_range(object_name: str, offset: int = 0, length: int | None = None):
    """Returns a urllib3 response object; caller must call .release_conn()."""
    _ensure_bucket()
    kwargs = {"offset": offset}
    if length is not None:
        kwargs["length"] = length
    return client().get_object(settings.minio_bucket, object_name, **kwargs)
