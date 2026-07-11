"""Media upload and delivery for lesson content: video, audio, images, documents.

Files live in object storage (MinIO/S3-compatible, see app/storage.py),
keyed as <tenant-slug>/<uuid><ext>. The public URL contract is unchanged
from the old local-disk version: /media/<tenant-slug>/<object-name>.
That route now streams from object storage instead of serving a local
file, including HTTP Range support so video seeking keeps working.
"""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import storage
from app.database import get_db
from app.deps import check_tenant_access, get_tenant, require_author
from app.models import MediaAsset, Tenant, User

router = APIRouter(prefix="/api/media", tags=["media"])
public_router = APIRouter(tags=["media"])

_KIND_BY_PREFIX = {"video/": "video", "audio/": "audio", "image/": "image"}
_ALLOWED_EXTENSIONS = {
    ".mp4", ".webm", ".mov", ".m4v",            # video
    ".mp3", ".wav", ".ogg", ".m4a",             # audio
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",  # image
    ".pdf", ".pptx", ".docx", ".xlsx", ".zip", ".txt", ".md",  # documents
}


@router.post("/upload")
def upload_media(
    file: UploadFile,
    tenant: Tenant = Depends(get_tenant),
    user: User = Depends(require_author),
    db: Session = Depends(get_db),
):
    check_tenant_access(user, tenant)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext or 'unknown'}' not allowed")
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] \
        or "application/octet-stream"
    try:
        object_name, size = storage.put_object(tenant.slug, file.filename or "", file.file, content_type)
    except storage.UploadTooLarge as e:
        raise HTTPException(413, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    kind = next((k for prefix, k in _KIND_BY_PREFIX.items() if content_type.startswith(prefix)), "file")
    asset = MediaAsset(
        tenant_id=tenant.id, filename=file.filename or object_name,
        stored_path=object_name,
        content_type=content_type, size_bytes=size, kind=kind, uploaded_by=user.id)
    db.add(asset)
    db.commit()
    return {
        "id": asset.id,
        "url": f"/media/{asset.stored_path}",
        "kind": kind,
        "filename": asset.filename,
        "size_bytes": size,
    }


@router.get("")
def list_media(
    tenant: Tenant = Depends(get_tenant),
    user: User = Depends(require_author),
    db: Session = Depends(get_db),
):
    check_tenant_access(user, tenant)
    assets = (db.query(MediaAsset).filter(MediaAsset.tenant_id == tenant.id)
              .order_by(MediaAsset.created_at.desc()).limit(200).all())
    return [
        {"id": a.id, "url": f"/media/{a.stored_path}",
         "kind": a.kind, "filename": a.filename, "size_bytes": a.size_bytes}
        for a in assets
    ]


def _stream_and_release(resp):
    """minio-py requires close() + release_conn() after reading, or the
    underlying connection pool leaks — see minio-py's own get_object docs."""
    try:
        yield from resp.stream(64 * 1024)
    finally:
        resp.close()
        resp.release_conn()


@public_router.get("/media/{tenant_slug}/{filename}")
def serve_media(tenant_slug: str, filename: str, request: Request):
    """Stream a media object from storage, honoring HTTP Range requests
    (needed for video/audio seeking — the old StaticFiles mount supported
    this for free; object storage needs it done explicitly)."""
    object_name = f"{tenant_slug}/{filename}"
    info = storage.stat_object(object_name)
    if info is None:
        raise HTTPException(404, "File not found")

    total = info.size
    content_type = info.content_type or "application/octet-stream"
    range_header = request.headers.get("range")

    if range_header:
        try:
            unit, rng = range_header.split("=")
            start_s, end_s = rng.split("-")
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else total - 1
        except (ValueError, IndexError):
            raise HTTPException(416, "Invalid Range header")
        if unit != "bytes" or start > end or end >= total:
            raise HTTPException(416, "Invalid Range header")
        length = end - start + 1
        resp = storage.get_object_range(object_name, offset=start, length=length)
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        }
        return StreamingResponse(
            _stream_and_release(resp), status_code=206, media_type=content_type, headers=headers)

    resp = storage.get_object_range(object_name)
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(total)}
    return StreamingResponse(
        _stream_and_release(resp), media_type=content_type, headers=headers)
