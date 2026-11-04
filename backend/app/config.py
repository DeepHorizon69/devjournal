import logging
from datetime import timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """DevJournal Application Configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DEVJOURNAL_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Field(
        default=Path(__file__).resolve().parent.parent.parent / "devjournal-data",
        description="Root data directory containing vault/ and devjournal.db",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    timezone: str = Field(
        default="UTC",
        description="IANA timezone name for daily journal date resolution (e.g. 'UTC', 'Asia/Jakarta')",
    )
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        description="Allowed CORS origins",
    )
    frontend_dist_dir: Path | None = Field(
        default=Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
        description="Directory containing built frontend static files",
    )

    @property
    def effective_tzinfo(self) -> tzinfo:
        """Resolve configured IANA timezone or safely fall back to UTC with a warning."""
        tz_name = (self.timezone or "UTC").strip()
        if tz_name.upper() == "UTC":
            return timezone.utc
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
            logger.warning(
                "Invalid or unavailable timezone %r (%s); falling back to UTC",
                self.timezone,
                exc,
            )
            return timezone.utc

    @property
    def vault_dir(self) -> Path:
        return self.data_dir / "vault"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "devjournal.db"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    def ensure_directories(self) -> None:
        """Ensure root data, vault, and backup directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
