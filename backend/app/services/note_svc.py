from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from app.config import settings
from app.db.connection import db_write_lock, get_db_connection, get_db_transaction
from app.models.api_models import (
    CreateNoteRequest,
    DeleteNoteResponse,
    EmptyTrashResponse,
    NoteDetailResponse,
    NotesListResponse,
    NoteSummaryResponse,
    PatchNoteRequest,
    UpdateNoteRequest,
)
from app.models.note import (
    VALID_DOMAINS,
    KnowledgeDomain,
    NoteFrontmatter,
    NoteStatus,
    NoteType,
)
from app.repositories.notes_repo import NotesRepository
from app.services.frontmatter_svc import (
    compute_content_hash,
    normalize_domains,
    normalize_tags,
    parse_markdown_note,
    serialize_note,
)
from app.services.indexer_svc import HashConflictError, IndexerService
from app.services.template_svc import TemplateService
from app.services.vault_storage import (
    CANONICAL_VAULT_FOLDERS,
    INBOX_FOLDER,
    NOTE_TYPE_TO_FOLDER,
    TRASH_FOLDER,
    InvalidEncodingError,
    InvalidInputError,
    InvalidTrashOperationError,
    NoteFileNotFoundError,
    NoteNotFoundError,
    PayloadTooLargeError,
    VaultStorageService,
    slugify_title,
)

MAX_MARKDOWN_IMPORT_BYTES = 10 * 1024 * 1024  # 10 MiB
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_and_normalize_domains(raw_domains: list[str]) -> list[KnowledgeDomain]:
    for item in raw_domains:
        if not isinstance(item, str) or item.strip().lower() not in VALID_DOMAINS:
            raise InvalidInputError(
                "INVALID_DOMAIN",
                f"Invalid knowledge domain: {item!r}",
                details={"valid_domains": list(VALID_DOMAINS.values())},
            )
    return normalize_domains(raw_domains)


def _validate_active_folder(folder: str) -> str:
    if folder not in CANONICAL_VAULT_FOLDERS or folder == TRASH_FOLDER:
        raise InvalidInputError(
            "INVALID_FOLDER",
            f"Folder must be an active canonical vault folder, got: {folder!r}",
            details={
                "valid_folders": [
                    f for f in CANONICAL_VAULT_FOLDERS if f != TRASH_FOLDER
                ]
            },
        )
    return folder


class NoteService:
    """Application service coordinating canonical Markdown vault writes and SQLite/FTS5 indexing."""

    def __init__(
        self,
        vault_storage: VaultStorageService | None = None,
        repo: NotesRepository | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else settings.db_path
        self.vault_storage = vault_storage or VaultStorageService(
            settings.vault_dir, db_path=self.db_path
        )
        self.repo = repo or NotesRepository()
        self.indexer = IndexerService(
            vault_storage=self.vault_storage,
            repo=self.repo,
            db_path=self.db_path,
        )
        self.templates = TemplateService()

    def _resolve_relocated_path(
        self, target_folder: str, current_rel_path: str, note_id: str
    ) -> str:
        """Preserve the existing filename stem when relocating folders unless occupied."""
        stem = Path(current_rel_path).stem or slugify_title("untitled", fallback_id=note_id)
        candidate_1 = f"{target_folder}/{stem}.md"
        if not self.vault_storage.resolve_safe_path(candidate_1).exists():
            return candidate_1

        short_id = (note_id or "note")[:8]
        candidate_2 = f"{target_folder}/{stem}-{short_id}.md"
        if not self.vault_storage.resolve_safe_path(candidate_2).exists():
            return candidate_2

        counter = 2
        while True:
            candidate_n = f"{target_folder}/{stem}-{short_id}-{counter}.md"
            if not self.vault_storage.resolve_safe_path(candidate_n).exists():
                return candidate_n
            counter += 1

    def list_notes(
        self,
        *,
        note_type: str | None = None,
        domain: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        status: str | None = None,
        trashed: bool = False,
        sort: str = "updated_desc",
        limit: int = 50,
        offset: int = 0,
    ) -> NotesListResponse:
        """List notes with optional filtering, sorting, and pagination."""
        if self.vault_storage.has_pending_move_journal():
            self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

        normalized_tag: str | None = None
        if tag is not None and tag.strip():
            norm_tags = normalize_tags([tag])
            normalized_tag = norm_tags[0] if norm_tags else tag.strip().lower()

        canonical_domain: str | None = None
        if domain is not None and domain.strip():
            canonical_domain = VALID_DOMAINS.get(domain.strip().lower(), domain.strip())

        with get_db_connection(self.db_path) as conn:
            total, records = self.repo.list_notes(
                conn,
                note_type=note_type,
                domain=canonical_domain,
                tag=normalized_tag,
                folder=folder,
                status=status,
                trashed=trashed,
                sort=sort,
                limit=limit,
                offset=offset,
            )

        return NotesListResponse(
            total=total,
            notes=[NoteSummaryResponse.from_record(rec) for rec in records],
        )

    def create_note(self, req: CreateNoteRequest) -> NoteDetailResponse:
        """Create a new note from scratch or from a built-in template."""
        clean_title = req.title.strip()
        if not clean_title:
            raise InvalidInputError("INVALID_TITLE", "Note title cannot be blank or whitespace-only")

        fields_set = req.model_fields_set

        if req.template_id is not None:
            tpl = self.templates.get_template(req.template_id)
            effective_type: NoteType = tpl.note_type
            effective_status: NoteStatus | None = tpl.default_status
            effective_folder: str = tpl.folder
            effective_body: str = tpl.body

            if "note_type" in fields_set and req.note_type is not None:
                effective_type = req.note_type
            if "status" in fields_set:
                effective_status = req.status
            if "folder" in fields_set and req.folder is not None:
                effective_folder = req.folder
            if "body" in fields_set and req.body is not None:
                effective_body = req.body
        else:
            effective_type = req.note_type if req.note_type is not None else "note"
            effective_status = req.status if "status" in fields_set else None
            effective_folder = (
                req.folder
                if ("folder" in fields_set and req.folder is not None)
                else NOTE_TYPE_TO_FOLDER[effective_type]
            )
            effective_body = req.body if req.body is not None else ""

        _validate_active_folder(effective_folder)
        domains = _validate_and_normalize_domains(req.domains)
        tags = normalize_tags(req.tags)

        with db_write_lock:
            self.vault_storage.ensure_vault_structure()
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            note_id = str(uuid.uuid4())
            now_iso = _now_utc_iso()
            rel_path = self.vault_storage.generate_unique_rel_path(
                effective_folder, clean_title, note_id
            )

            metadata = NoteFrontmatter(
                id=note_id,
                title=clean_title,
                type=effective_type,
                status=effective_status,
                created_at=now_iso,
                updated_at=now_iso,
                domains=domains,
                tags=tags,
                pinned=req.is_pinned,
                trashed=False,
                original_rel_path=None,
            )

            parsed, _ = self.indexer.write_and_index_note(
                metadata=metadata,
                body=effective_body,
                rel_path=rel_path,
            )

            with get_db_transaction(self.db_path) as conn:
                self.repo.touch_last_opened(conn, parsed.metadata.id, now_iso)
                rec = self.repo.get_note_by_id(conn, parsed.metadata.id)

            if rec is None:
                raise RuntimeError("Failed to retrieve created note from SQLite")

            return NoteDetailResponse.from_record_and_body(rec, parsed.body)

    def get_note(
        self, note_id: str, *, record_open: bool = True
    ) -> NoteDetailResponse:
        """Fetch full note detail under db_write_lock, auto-reconciling any external disk edit."""
        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                rec = self.repo.get_note_by_id(conn, note_id)

            if rec is None:
                raise NoteNotFoundError(note_id)

            try:
                raw_content, mtime = self.vault_storage.read_markdown(rec.rel_path)
            except NoteFileNotFoundError as exc:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_stale_note(conn, rec.id, rec.rel_path)
                raise NoteNotFoundError(note_id) from exc

            parsed = parse_markdown_note(
                raw_content, rel_path=rec.rel_path, file_mtime=mtime
            )
            now_iso = _now_utc_iso()

            if parsed.content_hash != rec.content_hash:
                parsed.metadata = parsed.metadata.model_copy(update={"id": rec.id})
                preserved_open = now_iso if record_open else rec.last_opened_at
                with get_db_transaction(self.db_path) as conn:
                    self.repo.upsert_parsed_note(
                        conn,
                        parsed,
                        preserved_last_opened_at=preserved_open,
                    )
                    if record_open:
                        self.repo.touch_last_opened(conn, rec.id, now_iso)
                    updated_rec = self.repo.get_note_by_id(conn, rec.id)
                if updated_rec is None:
                    raise NoteNotFoundError(note_id)
                rec = updated_rec
            else:
                if record_open:
                    with get_db_transaction(self.db_path) as conn:
                        self.repo.touch_last_opened(conn, rec.id, now_iso)
                    rec.last_opened_at = now_iso

            return NoteDetailResponse.from_record_and_body(rec, parsed.body)

    def _determine_target_folder(
        self,
        current_folder: str,
        current_type: NoteType,
        new_type: NoteType,
        explicit_folder: str | None,
        folder_in_fields_set: bool,
    ) -> str:
        """Apply Section 2.4 folder precedence and Inbox preservation rules."""
        if folder_in_fields_set and explicit_folder is not None:
            return _validate_active_folder(explicit_folder)

        if new_type != current_type:
            if current_folder == INBOX_FOLDER:
                return INBOX_FOLDER
            if current_folder == NOTE_TYPE_TO_FOLDER.get(current_type):
                return NOTE_TYPE_TO_FOLDER[new_type]
            return current_folder

        return current_folder

    def update_note(
        self, note_id: str, req: UpdateNoteRequest
    ) -> NoteDetailResponse:
        """Full note save/update (PUT) with strict optimistic concurrency and journaled folder moves."""
        clean_title = req.title.strip()
        if not clean_title:
            raise InvalidInputError("INVALID_TITLE", "Note title cannot be blank or whitespace-only")

        if not req.force and not req.expected_hash:
            raise InvalidInputError(
                "MISSING_EXPECTED_HASH",
                "expected_hash is required when force is false",
            )

        domains = _validate_and_normalize_domains(req.domains)
        tags = normalize_tags(req.tags)

        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                rec = self.repo.get_note_by_id(conn, note_id)

            if rec is None:
                raise NoteNotFoundError(note_id)

            if rec.is_trashed or rec.folder == TRASH_FOLDER:
                raise InvalidTrashOperationError(
                    "Cannot update a trashed note; restore it first"
                )

            try:
                existing_raw, _ = self.vault_storage.read_markdown(rec.rel_path)
            except NoteFileNotFoundError as exc:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_stale_note(conn, rec.id, rec.rel_path)
                raise NoteNotFoundError(note_id) from exc

            current_hash = compute_content_hash(existing_raw)
            if not req.force and req.expected_hash != current_hash:
                raise HashConflictError(
                    current_hash=current_hash,
                    expected_hash=req.expected_hash or "",
                )

            target_folder = self._determine_target_folder(
                current_folder=rec.folder,
                current_type=rec.note_type,
                new_type=req.note_type,
                explicit_folder=req.folder,
                folder_in_fields_set="folder" in req.model_fields_set,
            )

            if target_folder == rec.folder:
                target_rel_path = rec.rel_path
            else:
                target_rel_path = self._resolve_relocated_path(
                    target_folder, rec.rel_path, rec.id
                )

            now_iso = _now_utc_iso()
            metadata = NoteFrontmatter(
                id=rec.id,
                title=clean_title,
                type=req.note_type,
                status=req.status,
                created_at=rec.created_at,
                updated_at=now_iso,
                domains=domains,
                tags=tags,
                pinned=req.is_pinned,
                trashed=False,
                original_rel_path=None,
            )

            raw_md = serialize_note(metadata, req.body)

            if target_rel_path != rec.rel_path:
                _, mtime = self.vault_storage.move_note(
                    rec.rel_path,
                    target_rel_path,
                    updated_content=raw_md,
                    allow_overwrite=False,
                )
            else:
                _, mtime = self.vault_storage.write_markdown_atomic(
                    target_rel_path, raw_md
                )

            parsed = parse_markdown_note(
                raw_md, rel_path=target_rel_path, file_mtime=mtime
            )
            parsed.metadata = parsed.metadata.model_copy(update={"id": rec.id})

            with get_db_transaction(self.db_path) as conn:
                self.repo.upsert_parsed_note(
                    conn, parsed, preserved_last_opened_at=rec.last_opened_at
                )
                updated_rec = self.repo.get_note_by_id(conn, rec.id)

            if updated_rec is None:
                raise NoteNotFoundError(note_id)

            return NoteDetailResponse.from_record_and_body(updated_rec, parsed.body)

    def patch_note(
        self, note_id: str, req: PatchNoteRequest
    ) -> NoteDetailResponse:
        """Partial metadata update (PATCH) with mandatory expected_hash optimistic concurrency."""
        fields_set = req.model_fields_set

        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                rec = self.repo.get_note_by_id(conn, note_id)

            if rec is None:
                raise NoteNotFoundError(note_id)

            if rec.is_trashed or rec.folder == TRASH_FOLDER:
                raise InvalidTrashOperationError(
                    "Cannot update a trashed note; restore it first"
                )

            try:
                existing_raw, existing_mtime = self.vault_storage.read_markdown(
                    rec.rel_path
                )
            except NoteFileNotFoundError as exc:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_stale_note(conn, rec.id, rec.rel_path)
                raise NoteNotFoundError(note_id) from exc

            current_hash = compute_content_hash(existing_raw)
            if req.expected_hash != current_hash:
                raise HashConflictError(
                    current_hash=current_hash,
                    expected_hash=req.expected_hash,
                )

            existing_parsed = parse_markdown_note(
                existing_raw, rel_path=rec.rel_path, file_mtime=existing_mtime
            )

            new_title = rec.title
            if "title" in fields_set and req.title is not None:
                clean_title = req.title.strip()
                if not clean_title:
                    raise InvalidInputError(
                        "INVALID_TITLE", "Note title cannot be blank or whitespace-only"
                    )
                new_title = clean_title

            new_type: NoteType = (
                req.note_type
                if ("note_type" in fields_set and req.note_type is not None)
                else rec.note_type
            )
            new_status: NoteStatus | None = (
                req.status if "status" in fields_set else rec.status
            )
            new_domains: list[KnowledgeDomain] = (
                _validate_and_normalize_domains(req.domains)
                if ("domains" in fields_set and req.domains is not None)
                else list(rec.domains)
            )
            new_tags: list[str] = (
                normalize_tags(req.tags)
                if ("tags" in fields_set and req.tags is not None)
                else list(rec.tags)
            )
            new_pinned: bool = (
                req.is_pinned
                if ("is_pinned" in fields_set and req.is_pinned is not None)
                else rec.is_pinned
            )

            target_folder = self._determine_target_folder(
                current_folder=rec.folder,
                current_type=rec.note_type,
                new_type=new_type,
                explicit_folder=req.folder,
                folder_in_fields_set="folder" in fields_set,
            )

            if target_folder == rec.folder:
                target_rel_path = rec.rel_path
            else:
                target_rel_path = self._resolve_relocated_path(
                    target_folder, rec.rel_path, rec.id
                )

            now_iso = _now_utc_iso()
            metadata = NoteFrontmatter(
                id=rec.id,
                title=new_title,
                type=new_type,
                status=new_status,
                created_at=rec.created_at,
                updated_at=now_iso,
                domains=new_domains,
                tags=new_tags,
                pinned=new_pinned,
                trashed=False,
                original_rel_path=None,
            )

            raw_md = serialize_note(metadata, existing_parsed.body)

            if target_rel_path != rec.rel_path:
                _, mtime = self.vault_storage.move_note(
                    rec.rel_path,
                    target_rel_path,
                    updated_content=raw_md,
                    allow_overwrite=False,
                )
            else:
                _, mtime = self.vault_storage.write_markdown_atomic(
                    target_rel_path, raw_md
                )

            parsed = parse_markdown_note(
                raw_md, rel_path=target_rel_path, file_mtime=mtime
            )
            parsed.metadata = parsed.metadata.model_copy(update={"id": rec.id})

            with get_db_transaction(self.db_path) as conn:
                self.repo.upsert_parsed_note(
                    conn, parsed, preserved_last_opened_at=rec.last_opened_at
                )
                updated_rec = self.repo.get_note_by_id(conn, rec.id)

            if updated_rec is None:
                raise NoteNotFoundError(note_id)

            return NoteDetailResponse.from_record_and_body(updated_rec, parsed.body)

    def delete_note(
        self, note_id: str, *, permanent: bool = False
    ) -> DeleteNoteResponse:
        """Soft-delete an active note to 99-Trash/ or permanently delete an already-trashed note."""
        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                rec = self.repo.get_note_by_id(conn, note_id)

            if rec is None:
                raise NoteNotFoundError(note_id)

            if permanent:
                # Strict Trash-First Permanent Deletion Rule (P0-2)
                if not rec.is_trashed or rec.folder != TRASH_FOLDER:
                    raise InvalidTrashOperationError(
                        "Active notes cannot be permanently deleted directly; move the note to Trash first"
                    )
                try:
                    self.vault_storage.delete_permanently(rec.rel_path)
                except NoteFileNotFoundError:
                    pass

                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_note_by_id(conn, rec.id)

                return DeleteNoteResponse(
                    status="ok", deleted_id=rec.id, permanent=True
                )

            # Soft delete (permanent=False)
            if rec.is_trashed or rec.folder == TRASH_FOLDER:
                raise InvalidTrashOperationError(
                    f"Note {rec.id} is already in {TRASH_FOLDER}"
                )

            try:
                existing_raw, existing_mtime = self.vault_storage.read_markdown(
                    rec.rel_path
                )
            except NoteFileNotFoundError as exc:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_stale_note(conn, rec.id, rec.rel_path)
                raise NoteNotFoundError(note_id) from exc

            existing_parsed = parse_markdown_note(
                existing_raw, rel_path=rec.rel_path, file_mtime=existing_mtime
            )
            now_iso = _now_utc_iso()
            trashed_meta = existing_parsed.metadata.model_copy(
                update={
                    "id": rec.id,
                    "trashed": True,
                    "original_rel_path": rec.rel_path,
                    "updated_at": now_iso,
                }
            )
            trashed_raw = serialize_note(trashed_meta, existing_parsed.body)

            trash_rel_path, _, mtime = self.vault_storage.move_to_trash(
                rec.rel_path,
                note_id=rec.id,
                trashed_content=trashed_raw,
            )

            parsed_trashed = parse_markdown_note(
                trashed_raw, rel_path=trash_rel_path, file_mtime=mtime
            )
            parsed_trashed.metadata = parsed_trashed.metadata.model_copy(
                update={"id": rec.id}
            )

            with get_db_transaction(self.db_path) as conn:
                self.repo.upsert_parsed_note(
                    conn,
                    parsed_trashed,
                    preserved_last_opened_at=rec.last_opened_at,
                )

            return DeleteNoteResponse(
                status="ok", deleted_id=rec.id, permanent=False
            )

    def restore_note(self, note_id: str) -> NoteDetailResponse:
        """Restore a trashed note from 99-Trash/ back to its original or fallback active folder."""
        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                rec = self.repo.get_note_by_id(conn, note_id)

            if rec is None:
                raise NoteNotFoundError(note_id)

            if not rec.is_trashed or rec.folder != TRASH_FOLDER:
                raise InvalidTrashOperationError(
                    f"Note {rec.id} is not in {TRASH_FOLDER} and cannot be restored"
                )

            try:
                existing_raw, existing_mtime = self.vault_storage.read_markdown(
                    rec.rel_path
                )
            except NoteFileNotFoundError as exc:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_stale_note(conn, rec.id, rec.rel_path)
                raise NoteNotFoundError(note_id) from exc

            existing_parsed = parse_markdown_note(
                existing_raw, rel_path=rec.rel_path, file_mtime=existing_mtime
            )
            now_iso = _now_utc_iso()
            restored_meta = existing_parsed.metadata.model_copy(
                update={
                    "id": rec.id,
                    "trashed": False,
                    "original_rel_path": None,
                    "updated_at": now_iso,
                }
            )
            restored_raw = serialize_note(restored_meta, existing_parsed.body)
            fallback_folder = NOTE_TYPE_TO_FOLDER.get(rec.note_type, "10-Notes")

            restored_rel_path, _, mtime = self.vault_storage.restore_from_trash(
                rec.rel_path,
                original_rel_path=rec.original_rel_path,
                fallback_folder=fallback_folder,
                title=rec.title,
                note_id=rec.id,
                restored_content=restored_raw,
            )

            parsed_restored = parse_markdown_note(
                restored_raw, rel_path=restored_rel_path, file_mtime=mtime
            )
            parsed_restored.metadata = parsed_restored.metadata.model_copy(
                update={"id": rec.id}
            )

            with get_db_transaction(self.db_path) as conn:
                self.repo.upsert_parsed_note(
                    conn,
                    parsed_restored,
                    preserved_last_opened_at=rec.last_opened_at,
                )
                updated_rec = self.repo.get_note_by_id(conn, rec.id)

            if updated_rec is None:
                raise NoteNotFoundError(note_id)

            return NoteDetailResponse.from_record_and_body(
                updated_rec, parsed_restored.body
            )

    def empty_trash(self) -> EmptyTrashResponse:
        """Permanently delete all trashed notes (unbounded) and any unindexed orphan .md files in 99-Trash/."""
        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                trashed_records = self.repo.list_all_trashed_notes(conn)

            deleted_paths: set[str] = set()
            deleted_count = 0

            for rec in trashed_records:
                if PurePosixPath(rec.rel_path).parts[0] == TRASH_FOLDER:
                    try:
                        self.vault_storage.delete_permanently(rec.rel_path)
                        deleted_paths.add(rec.rel_path)
                    except NoteFileNotFoundError:
                        pass
                deleted_count += 1

            # Also unlink any unindexed orphan .md files physically inside 99-Trash/
            for rel_path, _abs_path, _mtime in self.vault_storage.iter_markdown_files():
                if (
                    PurePosixPath(rel_path).parts[0] == TRASH_FOLDER
                    and rel_path not in deleted_paths
                ):
                    try:
                        self.vault_storage.delete_permanently(rel_path)
                        deleted_count += 1
                    except NoteFileNotFoundError:
                        pass

            with get_db_transaction(self.db_path) as conn:
                for rec in trashed_records:
                    self.repo.delete_note_by_id(conn, rec.id)

            return EmptyTrashResponse(status="ok", deleted_count=deleted_count)

    def open_or_create_daily_note(
        self, date_str: str | None = None
    ) -> tuple[NoteDetailResponse, bool]:
        """Idempotently open or create vault/90-Daily/YYYY-MM-DD.md using the configured timezone."""
        if date_str is not None and date_str.strip():
            target_date = date_str.strip()
            if not _DATE_RE.match(target_date):
                raise InvalidInputError(
                    "INVALID_DATE",
                    f"Date must match YYYY-MM-DD format, got: {date_str!r}",
                )
            try:
                datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError as exc:
                raise InvalidInputError(
                    "INVALID_DATE",
                    f"Invalid calendar date: {date_str!r}",
                ) from exc
        else:
            target_date = datetime.now(settings.effective_tzinfo).strftime("%Y-%m-%d")

        daily_rel_path = f"90-Daily/{target_date}.md"

        with db_write_lock:
            self.vault_storage.ensure_vault_structure()
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                existing_rec = self.repo.get_note_by_rel_path(conn, daily_rel_path)

            daily_abs = self.vault_storage.resolve_safe_path(daily_rel_path)
            if existing_rec is not None and daily_abs.is_file():
                detail = self.get_note(existing_rec.id, record_open=True)
                return detail, False

            if daily_abs.is_file():
                # File exists on disk in 90-Daily/YYYY-MM-DD.md but was not yet indexed
                raw_content, mtime = self.vault_storage.read_markdown(daily_rel_path)
                parsed = parse_markdown_note(
                    raw_content, rel_path=daily_rel_path, file_mtime=mtime
                )
                now_iso = _now_utc_iso()
                with get_db_transaction(self.db_path) as conn:
                    self.repo.upsert_parsed_note(
                        conn, parsed, preserved_last_opened_at=now_iso
                    )
                detail = self.get_note(parsed.metadata.id, record_open=True)
                return detail, False

            # Create new daily note from 'daily' template
            tpl = self.templates.get_template("daily")
            note_id = str(uuid.uuid4())
            now_iso = _now_utc_iso()
            metadata = NoteFrontmatter(
                id=note_id,
                title=target_date,
                type="daily",
                status=tpl.default_status,
                created_at=now_iso,
                updated_at=now_iso,
                domains=[],
                tags=["daily"],
                pinned=False,
                trashed=False,
                original_rel_path=None,
            )

            parsed, _ = self.indexer.write_and_index_note(
                metadata=metadata,
                body=tpl.body,
                rel_path=daily_rel_path,
            )

            with get_db_transaction(self.db_path) as conn:
                self.repo.touch_last_opened(conn, parsed.metadata.id, now_iso)
                rec = self.repo.get_note_by_id(conn, parsed.metadata.id)

            if rec is None:
                raise RuntimeError("Failed to load newly created daily journal note")

            return NoteDetailResponse.from_record_and_body(rec, parsed.body), True

    def export_note_markdown(self, note_id: str) -> tuple[str, str]:
        """Return (raw_markdown_content, safe_download_filename) for a note."""
        with db_write_lock:
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            with get_db_connection(self.db_path) as conn:
                rec = self.repo.get_note_by_id(conn, note_id)

            if rec is None:
                raise NoteNotFoundError(note_id)

            try:
                raw_content, _ = self.vault_storage.read_markdown(rec.rel_path)
            except NoteFileNotFoundError as exc:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.delete_stale_note(conn, rec.id, rec.rel_path)
                raise NoteNotFoundError(note_id) from exc

            safe_slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", rec.slug or "note").strip("-") or "note"
            return raw_content, f"{safe_slug}.md"

    def import_markdown_file(
        self,
        filename: str,
        raw_bytes: bytes,
        folder: str = INBOX_FOLDER,
    ) -> NoteDetailResponse:
        """Import a raw .md file, injecting canonical frontmatter if missing and indexing immediately."""
        if not filename or not filename.lower().endswith(".md"):
            raise InvalidInputError(
                "INVALID_FILE_TYPE",
                "Only Markdown (.md) files can be imported",
            )

        if len(raw_bytes) > MAX_MARKDOWN_IMPORT_BYTES:
            raise PayloadTooLargeError(
                f"Markdown import exceeds maximum size of {MAX_MARKDOWN_IMPORT_BYTES} bytes",
                details={"max_bytes": MAX_MARKDOWN_IMPORT_BYTES},
            )

        _validate_active_folder(folder)

        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidEncodingError(
                f"Uploaded file {filename!r} is not valid UTF-8: {exc}"
            ) from exc

        stem_title = Path(filename).stem.replace("-", " ").replace("_", " ").strip() or "Imported Note"
        now_ts = datetime.now(timezone.utc).timestamp()

        with db_write_lock:
            self.vault_storage.ensure_vault_structure()
            if self.vault_storage.has_pending_move_journal():
                self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

            temp_rel = f"{folder}/{Path(filename).stem or 'imported'}.md"
            prelim = parse_markdown_note(
                raw_text, rel_path=temp_rel, file_mtime=now_ts
            )

            note_id = prelim.raw_frontmatter_id or str(uuid.uuid4())
            title = prelim.metadata.title if prelim.metadata.title != "Untitled" else stem_title
            rel_path = self.vault_storage.generate_unique_rel_path(
                folder, title, note_id
            )

            now_iso = _now_utc_iso()
            metadata = NoteFrontmatter(
                id=note_id,
                title=title,
                type=prelim.metadata.type,
                status=prelim.metadata.status,
                created_at=prelim.metadata.created_at if prelim.raw_frontmatter_id else now_iso,
                updated_at=now_iso,
                domains=prelim.metadata.domains,
                tags=prelim.metadata.tags,
                pinned=prelim.metadata.pinned,
                trashed=False,
                original_rel_path=None,
            )

            parsed, _ = self.indexer.write_and_index_note(
                metadata=metadata,
                body=prelim.body,
                rel_path=rel_path,
            )

            with get_db_transaction(self.db_path) as conn:
                self.repo.touch_last_opened(conn, parsed.metadata.id, now_iso)
                rec = self.repo.get_note_by_id(conn, parsed.metadata.id)

            if rec is None:
                raise RuntimeError("Failed to retrieve imported note from SQLite")

            return NoteDetailResponse.from_record_and_body(rec, parsed.body)
