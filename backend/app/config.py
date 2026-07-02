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

    # Local media storage root. Swap for an S3-backed implementation by
    # replacing app/routers/media.py storage helpers.
    media_root: Path = BASE_DIR / "uploads"
    max_upload_mb: int = 500

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    class Config:
        env_file = ".env"
        env_prefix = "LEARNSTACK_"


settings = Settings()
settings.media_root.mkdir(parents=True, exist_ok=True)
