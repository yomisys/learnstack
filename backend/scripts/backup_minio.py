"""Mirror every object in the media bucket to a local directory.

Run from backend/ (or inside the api container, where this is how it's
invoked from scripts/backup.sh):
    python -m scripts.backup_minio /app/backups/<date>/media

Companion to pg_dump for the Postgres side — together they're the two
halves of "back up everything a redeploy could otherwise lose."
"""
import sys
from pathlib import Path

from app import storage
from app.config import settings


def main(dest_dir: str) -> None:
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    client = storage.client()
    if not client.bucket_exists(settings.minio_bucket):
        print(f"Bucket '{settings.minio_bucket}' does not exist yet — nothing to back up.")
        return

    count = 0
    total_bytes = 0
    for obj in client.list_objects(settings.minio_bucket, recursive=True):
        local_path = dest / obj.object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client.fget_object(settings.minio_bucket, obj.object_name, str(local_path))
        count += 1
        total_bytes += obj.size or 0

    print(f"Backed up {count} objects ({total_bytes / 1024 / 1024:.1f} MB) to {dest}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.backup_minio <destination-dir>", file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
