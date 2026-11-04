from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.db.connection import get_db_connection
from app.models.api_models import (
    DashboardCounts,
    DashboardResponse,
    NoteSummaryResponse,
)
from app.repositories.notes_repo import NotesRepository
from app.services.vault_storage import VaultStorageService

router = APIRouter(prefix="/dashboard", tags=["Discovery"])


@router.get("", response_model=DashboardResponse)
def get_dashboard() -> DashboardResponse:
    """Return Overview dashboard counts, domain counts, recently opened, and recently updated notes."""
    vault = VaultStorageService(settings.vault_dir, db_path=settings.db_path)
    if vault.has_pending_move_journal():
        vault.recover_interrupted_moves(db_path=settings.db_path)

    repo = NotesRepository()
    with get_db_connection(settings.db_path) as conn:
        data = repo.get_dashboard_data(conn)

    return DashboardResponse(
        counts=DashboardCounts(**data["counts"]),
        domain_counts=data["domain_counts"],
        recently_opened=[
            NoteSummaryResponse.from_record(rec) for rec in data["recently_opened"]
        ],
        recently_updated=[
            NoteSummaryResponse.from_record(rec) for rec in data["recently_updated"]
        ],
    )
