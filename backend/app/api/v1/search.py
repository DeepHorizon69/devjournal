from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.api_models import SearchResponse
from app.models.note import KnowledgeDomain, NoteStatus, NoteType
from app.services.search_svc import SearchService

router = APIRouter(prefix="/search", tags=["Discovery"])


@router.get("", response_model=SearchResponse)
def search_notes(
    q: str = Query(default="", description="Full-text search query"),
    type: NoteType | None = Query(default=None, alias="type"),
    domain: KnowledgeDomain | None = Query(default=None),
    tag: str | None = Query(default=None),
    folder: str | None = Query(default=None),
    status_filter: NoteStatus | None = Query(default=None, alias="status"),
    trashed: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=100),
) -> SearchResponse:
    """Execute BM25-ranked FTS5 full-text search with collision-resistant per-query nonce highlight markers."""
    return SearchService().search(
        query=q,
        note_type=type,
        domain=domain,
        tag=tag,
        folder=folder,
        status=status_filter,
        trashed=trashed,
        limit=limit,
    )
