from __future__ import annotations

from fastapi import APIRouter, Body, Query, Response, status
from fastapi.responses import JSONResponse

from app.models.api_models import (
    CreateNoteRequest,
    DailyJournalRequest,
    DeleteNoteResponse,
    EmptyTrashResponse,
    NoteDetailResponse,
    NotesListResponse,
    PatchNoteRequest,
    SortOption,
    UpdateNoteRequest,
)
from app.models.note import KnowledgeDomain, NoteStatus, NoteType
from app.services.note_svc import NoteService

router = APIRouter(prefix="/notes", tags=["Notes"])


@router.get("", response_model=NotesListResponse)
def list_notes(
    type: NoteType | None = Query(default=None, alias="type"),
    domain: KnowledgeDomain | None = Query(default=None),
    tag: str | None = Query(default=None),
    folder: str | None = Query(default=None),
    status_filter: NoteStatus | None = Query(default=None, alias="status"),
    trashed: bool = Query(default=False),
    sort: SortOption = Query(default="updated_desc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotesListResponse:
    """List notes with optional filters, sorting, and pagination."""
    return NoteService().list_notes(
        note_type=type,
        domain=domain,
        tag=tag,
        folder=folder,
        status=status_filter,
        trashed=trashed,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=NoteDetailResponse, status_code=status.HTTP_201_CREATED)
def create_note(req: CreateNoteRequest) -> NoteDetailResponse:
    """Create a new note from scratch or by instantiating a built-in template."""
    return NoteService().create_note(req)


# Static sub-routes registered BEFORE parameterized /{note_id} routes
@router.post("/daily/today", response_model=NoteDetailResponse)
def open_or_create_daily_today(
    req: DailyJournalRequest | None = Body(default=None),
    date: str | None = Query(default=None),
) -> JSONResponse:
    """Idempotently open (200 OK) or create (201 Created) the Daily Journal note for today or a specified YYYY-MM-DD date."""
    target_date = req.date if (req is not None and req.date is not None) else date
    detail, created = NoteService().open_or_create_daily_note(date_str=target_date)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        content=detail.model_dump(),
    )


@router.delete("/trash", response_model=EmptyTrashResponse)
def empty_trash() -> EmptyTrashResponse:
    """Permanently delete all trashed notes (unbounded) and any orphan files in 99-Trash/."""
    return NoteService().empty_trash()


@router.get("/{note_id}", response_model=NoteDetailResponse)
def get_note(
    note_id: str,
    record_open: bool = Query(default=True),
) -> NoteDetailResponse:
    """Retrieve complete note metadata and Markdown body, auto-reconciling external disk edits."""
    return NoteService().get_note(note_id, record_open=record_open)


@router.put("/{note_id}", response_model=NoteDetailResponse)
def update_note(note_id: str, req: UpdateNoteRequest) -> NoteDetailResponse:
    """Atomically replace note content on disk and update SQLite with optimistic concurrency."""
    return NoteService().update_note(note_id, req)


@router.patch("/{note_id}", response_model=NoteDetailResponse)
def patch_note(note_id: str, req: PatchNoteRequest) -> NoteDetailResponse:
    """Partially update frontmatter metadata (pin, status, type, domains, tags, folder) with optimistic concurrency."""
    return NoteService().patch_note(note_id, req)


@router.delete("/{note_id}", response_model=DeleteNoteResponse)
def delete_note(
    note_id: str,
    permanent: bool = Query(default=False),
) -> DeleteNoteResponse:
    """Soft-delete an active note to 99-Trash/ or permanently delete an already-trashed note (?permanent=true)."""
    return NoteService().delete_note(note_id, permanent=permanent)


@router.post("/{note_id}/restore", response_model=NoteDetailResponse)
def restore_note(note_id: str) -> NoteDetailResponse:
    """Restore a note from 99-Trash/ back to its original or fallback active folder."""
    return NoteService().restore_note(note_id)


@router.get("/{note_id}/export")
def export_note(note_id: str) -> Response:
    """Download the raw canonical Markdown (.md) file with YAML frontmatter."""
    raw_content, safe_filename = NoteService().export_note_markdown(note_id)
    return Response(
        content=raw_content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )
