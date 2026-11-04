from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.db.connection import get_db_connection
from app.models.api_models import TaxonomyResponse
from app.repositories.notes_repo import NotesRepository
from app.services.vault_storage import VaultStorageService

router = APIRouter(prefix="/taxonomy", tags=["Discovery"])


@router.get("", response_model=TaxonomyResponse)
def get_taxonomy() -> TaxonomyResponse:
    """Return active note counts by type, domain, tag, folder, and total active/trashed."""
    vault = VaultStorageService(settings.vault_dir, db_path=settings.db_path)
    if vault.has_pending_move_journal():
        vault.recover_interrupted_moves(db_path=settings.db_path)

    repo = NotesRepository()
    with get_db_connection(settings.db_path) as conn:
        data = repo.get_taxonomy_counts(conn)
    return TaxonomyResponse(**data)
