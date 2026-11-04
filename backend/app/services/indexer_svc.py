from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field

from app.config import settings
from app.db.connection import db_write_lock, get_db_connection, get_db_transaction
from app.models.note import NoteFrontmatter, ParsedNote
from app.repositories.notes_repo import NotesRepository
from app.services.frontmatter_svc import (
    compute_content_hash,
    parse_markdown_note,
    serialize_note,
)
from app.services.vault_storage import (
    InvalidEncodingError,
    NoteFileNotFoundError,
    VaultError,
    VaultStorageService,
)

logger = logging.getLogger(__name__)


class HashConflictError(VaultError):
    """Raised when optimistic concurrency check fails (expected_hash != current_hash)."""

    def __init__(self, current_hash: str, expected_hash: str) -> None:
        self.current_hash = current_hash
        self.expected_hash = expected_hash
        super().__init__(
            f"Note content hash conflict: expected {expected_hash}, found {current_hash}"
        )


class ReindexResult(BaseModel):
    """Summary returned by startup vault reconciliation and full reindex runs."""

    status: str = "ok"
    indexed: int
    updated: int = 0
    unchanged: int = 0
    removed: int
    warnings: int = 0
    warning_details: list[str] = Field(default_factory=list)
    duration_ms: int


def compute_collision_id(raw_id: str, rel_path: str) -> str:
    """Compute a deterministic UUIDv5 for a note whose frontmatter UUID collides with another file."""
    norm_rel = PurePosixPath(rel_path.replace("\\", "/")).as_posix()
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"devjournal:collision:{raw_id}:{norm_rel}")
    )


class IndexerService:
    """Coordinates hash-verified vault delta reconciliation, full reindex, and write-then-index."""

    def __init__(
        self,
        vault_storage: VaultStorageService | None = None,
        repo: NotesRepository | None = None,
        db_path: Path | None = None,
    ) -> None:
        self.vault_storage = vault_storage or VaultStorageService(settings.vault_dir)
        self.repo = repo or NotesRepository()
        self.db_path = Path(db_path) if db_path is not None else settings.db_path

    def reconcile_vault(self) -> ReindexResult:
        """Hash-verified delta reconciler keeping filesystem scans outside the SQLite write tx."""
        start_ns = time.perf_counter_ns()
        indexed = 0
        updated = 0
        unchanged = 0
        removed = 0
        warnings = 0
        warning_details: list[str] = []

        with db_write_lock:
            self.vault_storage.recover_interrupted_moves(
                db_path=self.db_path, sync_db=False
            )

            # Phase A: Read-Only Manifest Snapshot
            with get_db_connection(self.db_path) as conn:
                manifest = self.repo.get_index_manifest(conn)
            existing_ids = {info["id"]: rel_p for rel_p, info in manifest.items()}

            # Phase B: Filesystem Walk, Strict UTF-8 Read, SHA-256 Verification & Selective Parsing
            disk_files = self.vault_storage.iter_markdown_files()
            to_upsert: list[tuple[ParsedNote, bool]] = []
            mtime_updates: list[tuple[str, str, float]] = []
            disk_rel_paths: set[str] = set()
            claimed_ids: dict[str, str] = {}

            for rel_path, _abs_path, mtime in disk_files:
                try:
                    raw_content, mtime = self.vault_storage.read_markdown(rel_path)
                except NoteFileNotFoundError:
                    continue
                except InvalidEncodingError as exc:
                    warnings += 1
                    msg = str(exc)
                    warning_details.append(msg)
                    logger.warning("Skipping non-UTF-8 file during reconciliation: %s", msg)
                    continue

                current_hash = compute_content_hash(raw_content)
                disk_rel_paths.add(rel_path)

                if (
                    rel_path in manifest
                    and manifest[rel_path]["content_hash"] == current_hash
                ):
                    manifest_id = manifest[rel_path]["id"]
                    # Check if manifest_id is an existing collision ID for an already-claimed UUID
                    matched_collision_source: tuple[str, str] | None = None
                    for claimed_id, owner_rel in claimed_ids.items():
                        if manifest_id == compute_collision_id(claimed_id, rel_path):
                            matched_collision_source = (claimed_id, owner_rel)
                            break

                    if matched_collision_source is not None:
                        dup_id, owner_rel = matched_collision_source
                        col_msg = (
                            f"Duplicate UUID {dup_id} in {rel_path} "
                            f"(already claimed by {owner_rel}); indexed with collision ID {manifest_id}"
                        )
                        warnings += 1
                        warning_details.append(col_msg)
                        logger.warning(col_msg)
                        claimed_ids[manifest_id] = rel_path
                        unchanged += 1
                        if abs(manifest[rel_path]["file_mtime"] - mtime) >= 1e-6:
                            mtime_updates.append((manifest_id, rel_path, mtime))
                        continue

                    if manifest_id not in claimed_ids:
                        claimed_ids[manifest_id] = rel_path
                        unchanged += 1
                        if abs(manifest[rel_path]["file_mtime"] - mtime) >= 1e-6:
                            mtime_updates.append((manifest_id, rel_path, mtime))
                        continue

                # Parse new, modified, or ID-colliding note
                parsed = parse_markdown_note(
                    raw_content, rel_path=rel_path, file_mtime=mtime
                )
                if parsed.had_parse_warning and parsed.parse_warning_message:
                    warnings += 1
                    warn_str = f"{rel_path}: {parsed.parse_warning_message}"
                    warning_details.append(warn_str)
                    logger.warning("Frontmatter warning in %s", warn_str)

                if parsed.metadata.id in claimed_ids:
                    orig_id = parsed.metadata.id
                    owner_rel = claimed_ids[orig_id]
                    collision_id = compute_collision_id(orig_id, rel_path)
                    col_msg = (
                        f"Duplicate UUID {orig_id} in {rel_path} "
                        f"(already claimed by {owner_rel}); indexed with collision ID {collision_id}"
                    )
                    warnings += 1
                    warning_details.append(col_msg)
                    logger.warning(col_msg)
                    parsed.metadata = parsed.metadata.model_copy(
                        update={"id": collision_id}
                    )
                    parsed.has_id_collision = True

                claimed_ids[parsed.metadata.id] = rel_path
                is_new = (rel_path not in manifest) and (
                    parsed.metadata.id not in existing_ids
                )
                to_upsert.append((parsed, is_new))

            stale_candidates = [
                (info["id"], stale_rel_path)
                for stale_rel_path, info in manifest.items()
                if stale_rel_path not in disk_rel_paths
            ]

            # Phase C: Short SQLite Write Transaction
            if to_upsert or mtime_updates or stale_candidates:
                with get_db_transaction(self.db_path) as conn:
                    for note_id, rel_p, mtime in mtime_updates:
                        self.repo.update_file_mtime(conn, note_id, rel_p, mtime)

                    for parsed, is_new in to_upsert:
                        self.repo.upsert_parsed_note(conn, parsed)
                        if is_new:
                            indexed += 1
                        else:
                            updated += 1

                    for stale_id, stale_rel_path in stale_candidates:
                        if self.repo.delete_stale_note(conn, stale_id, stale_rel_path):
                            removed += 1

        duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
        return ReindexResult(
            status="ok",
            indexed=indexed,
            updated=updated,
            unchanged=unchanged,
            removed=removed,
            warnings=warnings,
            warning_details=warning_details,
            duration_ms=duration_ms,
        )

    def full_reindex(self) -> ReindexResult:
        """Rebuild SQLite notes, junctions, and notes_fts from the vault while preserving last_opened_at."""
        start_ns = time.perf_counter_ns()
        warnings = 0
        warning_details: list[str] = []
        parsed_notes: list[ParsedNote] = []
        claimed_ids: dict[str, str] = {}

        with db_write_lock:
            self.vault_storage.recover_interrupted_moves(
                db_path=self.db_path, sync_db=False
            )

            # Phase A: Filesystem Walk & Full Parse (Outside SQLite Write Transaction)
            disk_files = self.vault_storage.iter_markdown_files()
            for rel_path, _abs_path, mtime in disk_files:
                try:
                    raw_content, mtime = self.vault_storage.read_markdown(rel_path)
                except NoteFileNotFoundError:
                    continue
                except InvalidEncodingError as exc:
                    warnings += 1
                    msg = str(exc)
                    warning_details.append(msg)
                    logger.warning("Skipping non-UTF-8 file during full reindex: %s", msg)
                    continue

                parsed = parse_markdown_note(
                    raw_content, rel_path=rel_path, file_mtime=mtime
                )
                if parsed.had_parse_warning and parsed.parse_warning_message:
                    warnings += 1
                    warn_str = f"{rel_path}: {parsed.parse_warning_message}"
                    warning_details.append(warn_str)
                    logger.warning("Frontmatter warning in %s", warn_str)

                if parsed.metadata.id in claimed_ids:
                    orig_id = parsed.metadata.id
                    owner_rel = claimed_ids[orig_id]
                    collision_id = compute_collision_id(orig_id, rel_path)
                    col_msg = (
                        f"Duplicate UUID {orig_id} in {rel_path} "
                        f"(already claimed by {owner_rel}); indexed with collision ID {collision_id}"
                    )
                    warnings += 1
                    warning_details.append(col_msg)
                    logger.warning(col_msg)
                    parsed.metadata = parsed.metadata.model_copy(
                        update={"id": collision_id}
                    )
                    parsed.has_id_collision = True

                claimed_ids[parsed.metadata.id] = rel_path
                parsed_notes.append(parsed)

            # Phase B: Short SQLite Write Transaction
            with get_db_transaction(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT id, last_opened_at FROM notes"
                ).fetchall()
                preserved_opened = {
                    row["id"]: row["last_opened_at"]
                    for row in rows
                    if row["last_opened_at"] is not None
                }
                previous_ids = {row["id"] for row in rows}

                conn.execute("DELETE FROM notes_fts;")
                conn.execute("DELETE FROM note_domains;")
                conn.execute("DELETE FROM note_tags;")
                conn.execute("DELETE FROM notes;")

                for parsed in parsed_notes:
                    self.repo.upsert_parsed_note(
                        conn,
                        parsed,
                        preserved_last_opened_at=preserved_opened.get(
                            parsed.metadata.id
                        ),
                    )

            removed = len(previous_ids - set(claimed_ids.keys()))

        duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
        return ReindexResult(
            status="ok",
            indexed=len(parsed_notes),
            updated=0,
            unchanged=0,
            removed=removed,
            warnings=warnings,
            warning_details=warning_details,
            duration_ms=duration_ms,
        )

    def write_and_index_note(
        self,
        metadata: NoteFrontmatter,
        body: str,
        rel_path: str,
        expected_hash: str | None = None,
        force: bool = False,
    ) -> tuple[ParsedNote, bool]:
        """Atomically write canonical Markdown note to disk and update SQLite/FTS5 index."""
        norm_rel_path = PurePosixPath(rel_path.replace("\\", "/")).as_posix()

        with db_write_lock:
            # 1. Optimistic concurrency check
            if expected_hash is not None and not force:
                try:
                    existing_text, _ = self.vault_storage.read_markdown(norm_rel_path)
                except NoteFileNotFoundError:
                    pass
                else:
                    current_hash = compute_content_hash(existing_text)
                    if current_hash != expected_hash:
                        raise HashConflictError(
                            current_hash=current_hash,
                            expected_hash=expected_hash,
                        )

            # 2. Duplicate UUID collision promotion check before serializing to disk
            with get_db_connection(self.db_path) as conn:
                owner_row = conn.execute(
                    "SELECT rel_path FROM notes WHERE id = ?",
                    (metadata.id,),
                ).fetchone()
            if owner_row is not None and owner_row["rel_path"] != norm_rel_path:
                other_rel = owner_row["rel_path"]
                try:
                    other_abs = self.vault_storage.resolve_safe_path(other_rel)
                    other_exists = other_abs.is_file()
                except Exception:
                    other_exists = False
                if other_exists:
                    promoted_id = compute_collision_id(metadata.id, norm_rel_path)
                    metadata = metadata.model_copy(update={"id": promoted_id})

            # 3. Serialize and atomically write to disk
            raw_md = serialize_note(metadata, body)
            _, mtime = self.vault_storage.write_markdown_atomic(norm_rel_path, raw_md)

            # 4. Parse and update SQLite + FTS5 index
            parsed = parse_markdown_note(
                raw_md, rel_path=norm_rel_path, file_mtime=mtime
            )
            index_ok = True
            try:
                with get_db_transaction(self.db_path) as conn:
                    self.repo.upsert_parsed_note(conn, parsed)
            except sqlite3.Error as exc:
                logger.error(
                    "SQLite index update failed after canonical Markdown write for %s: %s",
                    norm_rel_path,
                    exc,
                )
                index_ok = False

            return parsed, index_ok
