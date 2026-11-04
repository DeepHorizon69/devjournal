from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.db.connection import get_db_connection, get_db_transaction
from app.models.api_models import AppSettingsResponse, UpdateSettingsRequest
from app.repositories.settings_repo import SettingsRepository

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=AppSettingsResponse)
def get_settings() -> AppSettingsResponse:
    """Read application editor preferences (with automatic fallback for legacy keys)."""
    repo = SettingsRepository()
    with get_db_connection(settings.db_path) as conn:
        return repo.get_settings(conn)


@router.put("", response_model=AppSettingsResponse)
def update_settings(req: UpdateSettingsRequest) -> AppSettingsResponse:
    """Validate and persist editor preferences under canonical key 'editor_preferences'."""
    repo = SettingsRepository()
    with get_db_transaction(settings.db_path) as conn:
        return repo.update_settings(conn, req)
