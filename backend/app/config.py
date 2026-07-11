"""Application settings. All values overridable via environment / .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "LearnStack"
    debug: bool = False

    # SQLite by default so the platform runs with zero infrastructure;
    # point at Postgres in production (postgresql+psycopg://...).
    database_url: str = f"sqlite:///{BASE_DIR / 'learnstack.db'}"

    jwt_secret: str = "dev-only-secret-change-me-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    max_upload_mb: int = 500

    # Object storage (MinIO / any S3-compatible endpoint) for uploaded
    # lesson media. Media no longer lives on local disk, so it survives a
    # container redeploy — see app/storage.py.
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "learnstack"
    minio_secret_key: str = "learnstack-dev-secret"
    minio_bucket: str = "learnstack-media"
    minio_secure: bool = False

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Absolute origin used when channel messages must carry media links
    # (WhatsApp media messages, SMS fallback links). Set to the public API
    # domain in production.
    public_base_url: str = "http://localhost:8000"

    # Absolute origin of the frontend — printed on certificate PDFs as the
    # "verify this certificate at" link. Set to the public web domain in
    # production.
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_prefix = "LEARNSTACK_"


settings = Settings()
