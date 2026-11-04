from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import (
    dashboard,
    notes,
    search,
    settings as settings_router,
    system,
    taxonomy,
    templates,
)
from app.config import settings
from app.db.connection import RestoreInProgressError, init_db, maintenance_gate
from app.services.backup_svc import BackupService
from app.services.indexer_svc import HashConflictError, IndexerService
from app.services.vault_storage import (
    InvalidEncodingError,
    InvalidInputError,
    InvalidTrashOperationError,
    NoteFileExistsError,
    NoteFileNotFoundError,
    NoteNotFoundError,
    PathTraversalError,
    PayloadTooLargeError,
    VaultStorageService,
)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
        headers=headers,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories, canonical vault structure, SQLite WAL/schema,
    # fail-closed restore/move recovery, and delta sync
    settings.ensure_directories()
    vault_svc = VaultStorageService(settings.vault_dir, db_path=settings.db_path)
    vault_svc.ensure_vault_structure()
    init_db(settings.db_path)
    BackupService(settings.data_dir).recover_interrupted_restore_if_any()
    vault_svc.recover_interrupted_moves(db_path=settings.db_path)
    IndexerService(vault_storage=vault_svc, db_path=settings.db_path).reconcile_vault()
    yield


app = FastAPI(
    title="DevJournal API",
    version="0.1.0",
    description="Personal Engineering Knowledge Base API",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def maintenance_gate_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/")
    if path.startswith("/api/v1") and path not in (
        "/api/v1/system/health",
        "/api/v1/system/restore",
    ):
        try:
            with maintenance_gate.acquire_request_lease():
                return await call_next(request)
        except RestoreInProgressError as exc:
            return _error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                exc.code,
                exc.message,
                headers={"Retry-After": "2"},
            )
    return await call_next(request)


@app.exception_handler(RestoreInProgressError)
async def handle_restore_in_progress(
    request: Request, exc: RestoreInProgressError
) -> JSONResponse:
    return _error_response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        exc.code,
        exc.message,
        headers={"Retry-After": "2"},
    )


@app.exception_handler(NoteNotFoundError)
async def handle_note_not_found(
    request: Request, exc: NoteNotFoundError
) -> JSONResponse:
    return _error_response(
        status.HTTP_404_NOT_FOUND,
        "NOTE_NOT_FOUND",
        str(exc),
        details={"note_id": exc.note_id},
    )


@app.exception_handler(NoteFileNotFoundError)
async def handle_note_file_not_found(
    request: Request, exc: NoteFileNotFoundError
) -> JSONResponse:
    return _error_response(
        status.HTTP_404_NOT_FOUND,
        "NOTE_NOT_FOUND",
        f"Note file not found: {exc}",
    )


@app.exception_handler(HashConflictError)
async def handle_hash_conflict(
    request: Request, exc: HashConflictError
) -> JSONResponse:
    return _error_response(
        status.HTTP_409_CONFLICT,
        "CONFLICT_HASH_MISMATCH",
        "Note has been modified on the server since it was loaded.",
        details={
            "current_hash": exc.current_hash,
            "expected_hash": exc.expected_hash,
        },
    )


@app.exception_handler(NoteFileExistsError)
async def handle_note_file_exists(
    request: Request, exc: NoteFileExistsError
) -> JSONResponse:
    return _error_response(
        status.HTTP_409_CONFLICT,
        "NOTE_FILE_EXISTS",
        str(exc),
    )


@app.exception_handler(PathTraversalError)
async def handle_path_traversal(
    request: Request, exc: PathTraversalError
) -> JSONResponse:
    return _error_response(
        status.HTTP_400_BAD_REQUEST,
        "PATH_TRAVERSAL",
        str(exc),
    )


@app.exception_handler(InvalidTrashOperationError)
async def handle_invalid_trash_op(
    request: Request, exc: InvalidTrashOperationError
) -> JSONResponse:
    return _error_response(
        status.HTTP_400_BAD_REQUEST,
        "INVALID_TRASH_OPERATION",
        str(exc),
    )


@app.exception_handler(InvalidEncodingError)
async def handle_invalid_encoding(
    request: Request, exc: InvalidEncodingError
) -> JSONResponse:
    return _error_response(
        status.HTTP_400_BAD_REQUEST,
        "INVALID_ENCODING",
        str(exc),
    )


@app.exception_handler(InvalidInputError)
async def handle_invalid_input(
    request: Request, exc: InvalidInputError
) -> JSONResponse:
    return _error_response(
        status.HTTP_400_BAD_REQUEST,
        exc.code,
        exc.message,
        details=exc.details,
    )


@app.exception_handler(PayloadTooLargeError)
async def handle_payload_too_large(
    request: Request, exc: PayloadTooLargeError
) -> JSONResponse:
    return _error_response(
        status.HTTP_413_CONTENT_TOO_LARGE,
        exc.code,
        exc.message,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR",
        "Request validation failed",
        details={"errors": exc.errors()},
    )


# API v1 routes (22 endpoints total)
app.include_router(system.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(notes.router, prefix="/api/v1")
app.include_router(taxonomy.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")


# Serve compiled frontend in production if available
if settings.frontend_dist_dir and settings.frontend_dist_dir.exists():
    assets_dir = settings.frontend_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        index_file = settings.frontend_dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built"}
