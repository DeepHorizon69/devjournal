from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.note import KnowledgeDomain, NoteRecord, NoteStatus, NoteType

SortOption = Literal["updated_desc", "created_desc", "title_asc"]
EditorMode = Literal["raw", "split", "preview"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class TemplateItem(BaseModel):
    id: str
    name: str
    note_type: NoteType
    default_status: NoteStatus | None = None
    folder: str
    body: str


class TemplatesListResponse(BaseModel):
    templates: list[TemplateItem]


class NoteSummaryResponse(BaseModel):
    id: str
    title: str
    slug: str
    rel_path: str
    folder: str
    note_type: NoteType
    status: NoteStatus | None = None
    excerpt: str
    word_count: int
    reading_time_mins: int
    content_hash: str
    is_pinned: bool
    is_trashed: bool
    domains: list[KnowledgeDomain] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    last_opened_at: str | None = None

    @classmethod
    def from_record(cls, rec: NoteRecord) -> NoteSummaryResponse:
        return cls(
            id=rec.id,
            title=rec.title,
            slug=rec.slug,
            rel_path=rec.rel_path,
            folder=rec.folder,
            note_type=rec.note_type,
            status=rec.status,
            excerpt=rec.excerpt,
            word_count=rec.word_count,
            reading_time_mins=rec.reading_time_mins,
            content_hash=rec.content_hash,
            is_pinned=rec.is_pinned,
            is_trashed=rec.is_trashed,
            domains=list(rec.domains),
            tags=list(rec.tags),
            created_at=rec.created_at,
            updated_at=rec.updated_at,
            last_opened_at=rec.last_opened_at,
        )


class NoteDetailResponse(NoteSummaryResponse):
    body: str

    @classmethod
    def from_record_and_body(cls, rec: NoteRecord, body: str) -> NoteDetailResponse:
        return cls(
            id=rec.id,
            title=rec.title,
            slug=rec.slug,
            rel_path=rec.rel_path,
            folder=rec.folder,
            note_type=rec.note_type,
            status=rec.status,
            excerpt=rec.excerpt,
            word_count=rec.word_count,
            reading_time_mins=rec.reading_time_mins,
            content_hash=rec.content_hash,
            is_pinned=rec.is_pinned,
            is_trashed=rec.is_trashed,
            domains=list(rec.domains),
            tags=list(rec.tags),
            body=body,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
            last_opened_at=rec.last_opened_at,
        )


class NotesListResponse(BaseModel):
    total: int
    notes: list[NoteSummaryResponse]


class CreateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=250)
    note_type: NoteType | None = None
    status: NoteStatus | None = None
    domains: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    folder: str | None = None
    body: str | None = None
    template_id: str | None = None
    is_pinned: bool = False


class UpdateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=250)
    note_type: NoteType
    status: NoteStatus | None = None
    domains: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    folder: str | None = None
    is_pinned: bool = False
    body: str = ""
    expected_hash: str | None = Field(default=None, min_length=64, max_length=64)
    force: bool = False


class PatchNoteRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    note_type: NoteType | None = None
    status: NoteStatus | None = None
    domains: list[str] | None = None
    tags: list[str] | None = None
    folder: str | None = None
    is_pinned: bool | None = None
    expected_hash: str = Field(..., min_length=64, max_length=64)


class DeleteNoteResponse(BaseModel):
    status: str = "ok"
    deleted_id: str
    permanent: bool


class EmptyTrashResponse(BaseModel):
    status: str = "ok"
    deleted_count: int


class DailyJournalRequest(BaseModel):
    date: str | None = None


class TaxonomyResponse(BaseModel):
    types: dict[str, int]
    domains: dict[str, int]
    tags: dict[str, int]
    folders: dict[str, int]
    total_active: int
    total_trashed: int


class DashboardCounts(BaseModel):
    total_notes: int
    experiments: int
    troubleshooting: int
    projects: int
    daily: int
    snippets: int


class DashboardResponse(BaseModel):
    counts: DashboardCounts
    domain_counts: dict[KnowledgeDomain, int]
    recently_opened: list[NoteSummaryResponse]
    recently_updated: list[NoteSummaryResponse]


class SnippetSegment(BaseModel):
    text: str
    highlight: bool


class SearchResultItem(BaseModel):
    id: str
    title: str
    slug: str
    rel_path: str
    folder: str
    note_type: NoteType
    status: NoteStatus | None = None
    domains: list[KnowledgeDomain] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    updated_at: str
    snippet: str
    snippet_segments: list[SnippetSegment] = Field(default_factory=list)
    score: float


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    results: list[SearchResultItem]


class UpdateSettingsRequest(BaseModel):
    default_editor_mode: EditorMode = "split"
    editor_font_size: int = Field(default=14, ge=11, le=22)
    editor_word_wrap: bool = True
    autosave_delay_ms: int = Field(default=1000, ge=300, le=10000)


class AppSettingsResponse(BaseModel):
    default_editor_mode: EditorMode = "split"
    editor_font_size: int = 14
    editor_word_wrap: bool = True
    autosave_delay_ms: int = 1000
    updated_at: str


class BackupResponse(BaseModel):
    status: str = "ok"
    filename: str
    size_bytes: int
    created_at: str


class RestoreResponse(BaseModel):
    status: str = "ok"
    indexed: int
    safety_backup_filename: str
    duration_ms: int
