import os
import sqlite3
import tempfile
from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter(prefix="/system", tags=["System"])


class HealthResponse(BaseModel):
    status: str
    vault_writable: bool
    db_ok: bool
    indexed_notes: int
    data_dir: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Return system health status, verifying vault writability and database accessibility."""
    settings.ensure_directories()

    # Check vault writability
    vault_writable = False
    try:
        test_file = settings.vault_dir / f".health_check_{os.getpid()}"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        vault_writable = True
    except Exception:
        vault_writable = False

    # Check DB status
    db_ok = False
    indexed_notes = 0
    try:
        if settings.db_path.exists():
            with sqlite3.connect(settings.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='notes'")
                if cursor.fetchone()[0] > 0:
                    cursor.execute("SELECT count(*) FROM notes WHERE is_trashed = 0")
                    indexed_notes = cursor.fetchone()[0]
                db_ok = True
        else:
            # DB file doesn't exist yet, but parent directory is writable
            db_ok = settings.data_dir.exists() and os.access(settings.data_dir, os.W_OK)
    except Exception:
        db_ok = False

    return HealthResponse(
        status="ok" if (vault_writable and db_ok) else "degraded",
        vault_writable=vault_writable,
        db_ok=db_ok,
        indexed_notes=indexed_notes,
        data_dir=str(settings.data_dir)
    )
