from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.db.connection import get_db_connection, maintenance_gate
from app.models.api_models import BackupResponse, NoteDetailResponse, RestoreResponse
from app.repositories.notes_repo import NotesRepository
from app.services.backup_svc import BackupService
from app.services.indexer_svc import IndexerService, ReindexResult
from app.services.note_svc import MAX_MARKDOWN_IMPORT_BYTES, NoteService
from app.services.vault_storage import INBOX_FOLDER, PayloadTooLargeError, VaultStorageService

router = APIRouter(prefix="/system", tags=["System"])


class HealthResponse(BaseModel):
    status: str
    vault_writable: bool
    db_ok: bool
    indexed_notes: int
    data_dir: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return system health status, reporting 'maintenance' during restore or 'degraded' on recovery fault."""
    if maintenance_gate.is_restore_in_progress:
        return HealthResponse(
            status="maintenance",
            vault_writable=True,
            db_ok=True,
            indexed_notes=0,
            data_dir=str(settings.data_dir),
        )

    if maintenance_gate.is_degraded:
        return HealthResponse(
            status="degraded",
            vault_writable=False,
            db_ok=False,
            indexed_notes=0,
            data_dir=str(settings.data_dir),
        )

    settings.ensure_directories()
    VaultStorageService(settings.vault_dir).ensure_vault_structure()

    # Check vault writability without polluting vault_dir with dotfile probes
    vault_writable = False
    try:
        probe_file = settings.data_dir / f".health_check_{os.getpid()}"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        vault_writable = settings.vault_dir.is_dir() and os.access(
            settings.vault_dir, os.W_OK
        )
    except Exception:
        vault_writable = False

    # Check DB status
    db_ok = False
    indexed_notes = 0
    try:
        if settings.db_path.exists():
            with get_db_connection(settings.db_path) as conn:
                row = conn.execute(
                    "SELECT count(*) AS cnt FROM sqlite_master WHERE type='table' AND name='notes'"
                ).fetchone()
                if row is not None and int(row["cnt"]) > 0:
                    indexed_notes = NotesRepository().count_active_notes(conn)
                db_ok = True
        else:
            db_ok = settings.data_dir.exists() and os.access(
                settings.data_dir, os.W_OK
            )
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if (vault_writable and db_ok) else "degraded",
        vault_writable=vault_writable,
        db_ok=db_ok,
        indexed_notes=indexed_notes,
        data_dir=str(settings.data_dir),
    )


@router.post("/reindex", response_model=ReindexResult)
def reindex_vault() -> ReindexResult:
    """Perform a full vault reindex into SQLite and FTS5."""
    settings.ensure_directories()
    VaultStorageService(settings.vault_dir).ensure_vault_structure()
    return IndexerService().full_reindex()


@router.post(
    "/import-md",
    response_model=NoteDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_markdown(
    file: UploadFile = File(...),
    folder: str = Form(default=INBOX_FOLDER),
) -> NoteDetailResponse:
    """Import an uploaded Markdown (.md) file into the specified active vault folder."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_MARKDOWN_IMPORT_BYTES:
            raise PayloadTooLargeError(
                f"Markdown import exceeds maximum size of {MAX_MARKDOWN_IMPORT_BYTES} bytes",
                details={"max_bytes": MAX_MARKDOWN_IMPORT_BYTES},
            )
        chunks.append(chunk)

    raw_bytes = b"".join(chunks)
    return NoteService().import_markdown_file(
        filename=file.filename or "",
        raw_bytes=raw_bytes,
        folder=folder,
    )


@router.post("/backup", response_model=BackupResponse)
def create_backup() -> BackupResponse:
    """Create a full-snapshot .zip archive containing backup-manifest.json, devjournal.db, and vault/."""
    return BackupService().create_backup()


@router.get("/backups/{filename}")
def download_backup(filename: str) -> FileResponse:
    """Download a generated backup .zip archive by strictly validated filename."""
    resolved_path = BackupService().resolve_backup_download_path(filename)
    return FileResponse(
        path=resolved_path,
        media_type="application/zip",
        filename=filename,
    )


@router.post("/restore", response_model=RestoreResponse)
def restore_backup(file: UploadFile = File(...)) -> RestoreResponse:
    """Restore a full-snapshot .zip backup archive with active-request draining and journaled rollback."""
    return BackupService().restore_from_stream(file.file)
