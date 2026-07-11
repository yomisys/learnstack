#!/usr/bin/env bash
# Back up Postgres + MinIO media to ./backups/<date>/, then prune backups
# older than RETENTION_DAYS. Run from the repo root:
#   ./scripts/backup.sh
#
# To schedule (crontab -e), e.g. nightly at 2am:
#   0 2 * * * cd /path/to/learnstack && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DATE="$(date +%Y-%m-%d_%H%M%S)"
OUT_DIR="backups/$DATE"
mkdir -p "$OUT_DIR"

echo "[$DATE] Backing up Postgres..."
docker compose exec -T db pg_dump -U learnstack learnstack | gzip > "$OUT_DIR/postgres.sql.gz"
echo "  -> $OUT_DIR/postgres.sql.gz ($(du -h "$OUT_DIR/postgres.sql.gz" | cut -f1))"

echo "[$DATE] Backing up media (MinIO)..."
# MSYS_NO_PATHCONV: on Git Bash for Windows, a bare /app/... argument gets
# silently rewritten to a Windows path before docker ever sees it, which
# corrupts this into a bogus path inside the container instead of the
# bind-mounted backups dir. Harmless (and unset) on real Linux hosts.
MSYS_NO_PATHCONV=1 docker compose exec -T api python -m scripts.backup_minio "/app/backups/$DATE/media"
if [ ! -d "$OUT_DIR/media" ]; then
  echo "ERROR: expected $OUT_DIR/media to exist after the backup ran — the container likely wrote somewhere else." >&2
  exit 1
fi
echo "  -> $OUT_DIR/media/ ($(find "$OUT_DIR/media" -type f | wc -l) files)"

echo "[$DATE] Pruning backups older than $RETENTION_DAYS days..."
find backups -maxdepth 1 -type d -name '20*' -mtime "+$RETENTION_DAYS" -exec rm -rf {} \;

echo "[$DATE] Backup complete."
