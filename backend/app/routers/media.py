"""Media upload for lesson content: video, audio, images, documents.

Files are stored under uploads/<tenant-slug>/ and served at /media/....
To move to S3/GCS later, replace _store() and keep the returned URL contract.
"""
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import check_tenant_access, get_tenant, require_author
from app.models import MediaAsset, Tenant, User

router = APIRouter(prefix="/api/media", tags=["media"])

_KIND_BY_PREFIX = {"video/": "video", "audio/": "audio", "image/": "image"}
_ALLOWED_EXTENSIONS = {
    ".mp4", ".webm", ".mov", ".m4v",            # video
    ".mp3", ".wav", ".ogg", ".m4a",             # audio
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",  # image
    ".pdf", ".pptx", ".docx", ".xlsx", ".zip", ".txt", ".md",  # documents
}
_CHUNK = 1024 * 1024


def _store(tenant_slug: str, upload: UploadFile) -> tuple[Path, int]:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext or 'unknown'}' not allowed")
    tenant_dir = settings.media_root / tenant_slug
    tenant_dir.mkdir(parents=True, exist_ok=True)
    dest = tenant_dir / f"{uuid.uuid4().hex}{ext}"
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as out:
        while chunk := upload.file.read(_CHUNK):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
            out.write(chunk)
    return dest, size


@router.post("/upload")
def upload_media(
    file: UploadFile,
    tenant: Tenant = Depends(get_tenant),
    user: User = Depends(require_author),
    db: Session = Depends(get_db),
):
    check_tenant_access(user, tenant)
    dest, size = _store(tenant.slug, file)
    content_type = file.content_type or mimetypes.guess_type(dest.name)[0] or "application/octet-stream"
    kind = next((k for prefix, k in _KIND_BY_PREFIX.items() if content_type.startswith(prefix)), "file")
    asset = MediaAsset(
        tenant_id=tenant.id, filename=file.filename or dest.name,
        stored_path=str(dest.relative_to(settings.media_root)),
        content_type=content_type, size_bytes=size, kind=kind, uploaded_by=user.id)
    db.add(asset)
    db.commit()
    return {
        "id": asset.id,
        "url": f"/media/{asset.stored_path.replace(chr(92), '/')}",
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
        {"id": a.id, "url": f"/media/{a.stored_path.replace(chr(92), '/')}",
         "kind": a.kind, "filename": a.filename, "size_bytes": a.size_bytes}
        for a in assets
    ]
