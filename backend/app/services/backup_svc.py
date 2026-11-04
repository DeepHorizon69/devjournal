from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from app.config import settings
from app.db.connection import (
    create_connection,
    db_write_lock,
    get_db_connection,
    get_db_transaction,
    init_db,
    maintenance_gate,
)
from app.models.api_models import BackupResponse, RestoreResponse
from app.services.indexer_svc import IndexerService, ReindexResult
from app.services.vault_storage import (
    CANONICAL_VAULT_FOLDERS,
    InvalidInputError,
    NoteNotFoundError,
    PayloadTooLargeError,
    VaultStorageService,
    _fsync_dir_posix,
)

logger = logging.getLogger(__name__)

BACKUP_FORMAT_VERSION = 1
MAX_BACKUP_NOTE_FILES = 10_000
MAX_ARCHIVE_ENTRIES = 10_050
MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024  # 250 MiB
MAX_COMPRESSED_UPLOAD_BYTES = 260 * 1024 * 1024  # 260 MiB
STREAM_CHUNK_BYTES = 64 * 1024  # 64 KiB

BACKUP_FILENAME_RE = re.compile(
    r"^devjournal-backup-\d{8}-\d{6}(?:-[a-f0-9]{8}|-pre-restore-[a-f0-9]{8})?\.zip$"
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json_atomic(target_path: Path, payload: dict[str, Any]) -> None:
    """Atomically write and fsync a JSON file and its parent directory."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.parent / f".tmp-{uuid.uuid4().hex}-{target_path.name}"
    raw_bytes = json.dumps(payload, indent=2).encode("utf-8")
    try:
        with open(temp_path, "wb") as f:
            f.write(raw_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, target_path)
        _fsync_dir_posix(target_path.parent)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


class BackupService:
    """Coordinates lock-protected full-snapshot ZIP backups and journaled crash-recoverable restores."""

    def __init__(
        self,
        data_dir: Path | None = None,
        *,
        max_backup_note_files: int = MAX_BACKUP_NOTE_FILES,
        max_archive_entries: int = MAX_ARCHIVE_ENTRIES,
        max_uncompressed_bytes: int = MAX_UNCOMPRESSED_BYTES,
        max_compressed_upload_bytes: int = MAX_COMPRESSED_UPLOAD_BYTES,
    ) -> None:
        self.data_dir = (
            Path(data_dir) if data_dir is not None else settings.data_dir
        ).resolve()
        self.vault_dir = self.data_dir / "vault"
        self.db_path = self.data_dir / "devjournal.db"
        self.backups_dir = self.data_dir / "backups"
        self.journal_path = self.data_dir / ".restore-journal.json"

        self.max_backup_note_files = max_backup_note_files
        self.max_archive_entries = max_archive_entries
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_compressed_upload_bytes = max_compressed_upload_bytes

        self.vault_storage = VaultStorageService(self.vault_dir, db_path=self.db_path)

    def _ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.vault_storage.ensure_vault_structure()
        if not self.db_path.exists():
            init_db(self.db_path)

    def create_backup(self) -> BackupResponse:
        """Create a full-snapshot .zip archive under db_write_lock with manifest and size guarantees."""
        with db_write_lock:
            return self._create_backup_locked()

    def _create_backup_locked(
        self, *, safety_op_id: str | None = None
    ) -> BackupResponse:
        """Internal backup builder called while holding db_write_lock."""
        self._ensure_dirs()
        if self.vault_storage.has_pending_move_journal():
            self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

        op_id = safety_op_id or uuid.uuid4().hex
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.strftime("%Y%m%d-%H%M%S")
        created_at = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        if safety_op_id is not None:
            filename = f"devjournal-backup-{ts_str}-pre-restore-{op_id[:8]}.zip"
        else:
            candidate_name = f"devjournal-backup-{ts_str}.zip"
            if (self.backups_dir / candidate_name).exists():
                filename = f"devjournal-backup-{ts_str}-{op_id[:8]}.zip"
            else:
                filename = candidate_name

        final_zip_path = self.backups_dir / filename
        temp_db = self.backups_dir / f".tmp-db-{op_id}.db"
        temp_zip = self.backups_dir / f".tmp-backup-{op_id}.zip"

        try:
            # 1. Hot-snapshot SQLite database
            with get_db_connection(self.db_path) as src_conn:
                dst_conn = sqlite3.connect(str(temp_db))
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()

            db_bytes = temp_db.read_bytes()
            db_size = len(db_bytes)
            db_sha256 = hashlib.sha256(db_bytes).hexdigest()

            # 2. Walk canonical vault Markdown files and verify counts/sizes
            disk_files = self.vault_storage.iter_markdown_files()
            note_file_count = len(disk_files)
            if note_file_count > self.max_backup_note_files:
                raise PayloadTooLargeError(
                    f"Vault contains {note_file_count} Markdown files, exceeding backup limit of {self.max_backup_note_files}",
                    details={
                        "note_file_count": note_file_count,
                        "max_backup_note_files": self.max_backup_note_files,
                    },
                )

            files_manifest: dict[str, str] = {}
            md_payloads: list[tuple[str, bytes]] = []
            md_uncompressed_bytes = 0

            for rel_path, abs_path, _mtime in disk_files:
                raw_md_bytes = abs_path.read_bytes()
                # Verify valid UTF-8
                raw_md_bytes.decode("utf-8")
                md_uncompressed_bytes += len(raw_md_bytes)
                if db_size + md_uncompressed_bytes > self.max_uncompressed_bytes:
                    raise PayloadTooLargeError(
                        f"Backup uncompressed size exceeds maximum limit of {self.max_uncompressed_bytes} bytes",
                        details={"max_uncompressed_bytes": self.max_uncompressed_bytes},
                    )
                arc_path = f"vault/{rel_path}"
                files_manifest[arc_path] = hashlib.sha256(raw_md_bytes).hexdigest()
                md_payloads.append((arc_path, raw_md_bytes))

            total_uncompressed_bytes = db_size + md_uncompressed_bytes
            manifest_data = {
                "format_version": BACKUP_FORMAT_VERSION,
                "created_at": created_at,
                "app_version": "0.1.0",
                "note_file_count": note_file_count,
                "total_uncompressed_bytes": total_uncompressed_bytes,
                "db_sha256": db_sha256,
                "files": files_manifest,
            }
            manifest_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")

            if total_uncompressed_bytes + len(manifest_bytes) > self.max_uncompressed_bytes:
                raise PayloadTooLargeError(
                    f"Backup uncompressed size exceeds maximum limit of {self.max_uncompressed_bytes} bytes",
                    details={"max_uncompressed_bytes": self.max_uncompressed_bytes},
                )

            # 3. Write ZIP archive to temporary file and fsync before promotion
            with open(temp_zip, "wb") as raw_zf:
                with zipfile.ZipFile(
                    raw_zf, mode="w", compression=zipfile.ZIP_DEFLATED
                ) as zf:
                    zf.writestr("backup-manifest.json", manifest_bytes)
                    zf.writestr("devjournal.db", db_bytes)
                    zf.writestr("vault/", b"")
                    for folder in CANONICAL_VAULT_FOLDERS:
                        zf.writestr(f"vault/{folder}/", b"")
                    for arc_path, data in md_payloads:
                        zf.writestr(arc_path, data)

                    entry_count = len(zf.infolist())
                    if entry_count > self.max_archive_entries:
                        raise PayloadTooLargeError(
                            f"Backup archive entry count ({entry_count}) exceeds limit of {self.max_archive_entries}",
                            details={
                                "entry_count": entry_count,
                                "max_archive_entries": self.max_archive_entries,
                            },
                        )

                raw_zf.flush()
                os.fsync(raw_zf.fileno())

            compressed_size = temp_zip.stat().st_size
            if compressed_size > self.max_compressed_upload_bytes:
                raise PayloadTooLargeError(
                    f"Compressed backup archive ({compressed_size} bytes) exceeds limit of {self.max_compressed_upload_bytes} bytes",
                    details={
                        "compressed_size": compressed_size,
                        "max_compressed_upload_bytes": self.max_compressed_upload_bytes,
                    },
                )

            os.replace(temp_zip, final_zip_path)
            _fsync_dir_posix(self.backups_dir)

            return BackupResponse(
                status="ok",
                filename=filename,
                size_bytes=compressed_size,
                created_at=created_at,
            )
        finally:
            temp_db.unlink(missing_ok=True)
            temp_zip.unlink(missing_ok=True)

    def resolve_backup_download_path(self, filename: str) -> Path:
        """Strictly validate a backup filename and return its resolved Path inside backups_dir."""
        if (
            not filename
            or "/" in filename
            or "\\" in filename
            or ".." in filename
            or "\x00" in filename
            or not BACKUP_FILENAME_RE.match(filename)
        ):
            raise InvalidInputError(
                "INVALID_BACKUP_FILENAME",
                f"Invalid backup filename: {filename!r}",
            )

        self.backups_dir.mkdir(parents=True, exist_ok=True)
        candidate = self.backups_dir / filename
        if candidate.is_symlink():
            raise InvalidInputError(
                "INVALID_BACKUP_FILENAME",
                f"Backup file cannot be a symlink: {filename!r}",
            )

        resolved = candidate.resolve()
        if resolved.parent != self.backups_dir.resolve():
            raise InvalidInputError(
                "INVALID_BACKUP_FILENAME",
                f"Backup path escapes backups directory: {filename!r}",
            )

        if not resolved.is_file():
            raise NoteNotFoundError(filename)

        return resolved

    def _validate_archive_member_name(self, info: zipfile.ZipInfo) -> tuple[str, str]:
        """Validate a ZipInfo entry against path traversal, symlink, and strict allowlist rules.

        Returns (normalized_posix_name, member_kind) where member_kind is one of:
        'manifest', 'db', 'dir', 'markdown'.
        """
        raw_name = info.filename
        if not raw_name or "\x00" in raw_name:
            raise InvalidInputError("INVALID_ARCHIVE", "Archive contains empty or NUL filename")

        if raw_name.startswith(("/", "\\")) or _WINDOWS_DRIVE_RE.match(raw_name):
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Archive member has absolute or drive-prefixed path: {raw_name!r}",
            )

        # Reject symlinks
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == 0o120000:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Archive contains disallowed symlink entry: {raw_name!r}",
            )

        norm = raw_name.replace("\\", "/")
        is_dir = norm.endswith("/") or info.is_dir()
        segments = [seg for seg in norm.split("/") if seg != ""]
        if not segments or any(seg in (".", "..") for seg in segments):
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Archive contains path traversal segment: {raw_name!r}",
            )

        pure = PurePosixPath("/".join(segments))
        norm_posix = pure.as_posix() + ("/" if is_dir else "")

        if norm_posix == "backup-manifest.json" and not is_dir:
            return "backup-manifest.json", "manifest"

        if norm_posix == "devjournal.db" and not is_dir:
            return "devjournal.db", "db"

        if norm_posix == "vault/":
            return "vault/", "dir"

        if pure.parts[0] != "vault" or len(pure.parts) < 2:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Unknown or disallowed archive member: {raw_name!r}",
            )

        canonical_folder = pure.parts[1]
        if canonical_folder not in CANONICAL_VAULT_FOLDERS:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Disallowed vault folder in archive: {canonical_folder!r}",
            )

        # Disallow hidden files/directories inside vault/
        if any(part.startswith(".") for part in pure.parts[1:]):
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Hidden files or directories are not permitted in vault archive: {raw_name!r}",
            )

        if is_dir:
            return norm_posix, "dir"

        if len(pure.parts) < 3 or not pure.parts[-1].lower().endswith(".md"):
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Only Markdown (.md) files are allowed inside vault folders: {raw_name!r}",
            )

        return norm_posix, "markdown"

    def _stage_and_validate_archive(
        self, zip_path: Path, staging_dir: Path
    ) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
        """Extract and validate a backup .zip in staging_dir before acquiring maintenance or locks.

        Returns (snapshot_settings_rows, snapshot_last_opened_map).
        """
        try:
            zf_test = zipfile.ZipFile(zip_path, mode="r")
        except (zipfile.BadZipFile, OSError) as exc:
            raise InvalidInputError(
                "INVALID_ARCHIVE", f"Uploaded file is not a valid ZIP archive: {exc}"
            ) from exc

        with zf_test as zf:
            infos = zf.infolist()
            if len(infos) > self.max_archive_entries:
                raise InvalidInputError(
                    "INVALID_ARCHIVE",
                    f"Archive contains {len(infos)} entries, exceeding maximum of {self.max_archive_entries}",
                )

            seen_paths: set[str] = set()
            has_manifest = False
            has_db = False
            validated_entries: list[tuple[zipfile.ZipInfo, str, str]] = []

            for info in infos:
                norm_name, kind = self._validate_archive_member_name(info)
                if norm_name in seen_paths:
                    raise InvalidInputError(
                        "INVALID_ARCHIVE",
                        f"Duplicate archive entry detected: {norm_name!r}",
                    )
                seen_paths.add(norm_name)
                if kind == "manifest":
                    has_manifest = True
                elif kind == "db":
                    has_db = True
                validated_entries.append((info, norm_name, kind))

            if not has_manifest:
                raise InvalidInputError(
                    "INVALID_ARCHIVE",
                    "Archive is missing required backup-manifest.json",
                )
            if not has_db:
                raise InvalidInputError(
                    "INVALID_ARCHIVE",
                    "Archive is missing required devjournal.db snapshot",
                )

            staging_vault = staging_dir / "vault"
            staging_vault.mkdir(parents=True, exist_ok=True)
            for folder in CANONICAL_VAULT_FOLDERS:
                (staging_vault / folder).mkdir(parents=True, exist_ok=True)

            total_extracted_bytes = 0
            actual_db_plus_md_bytes = 0
            actual_db_sha256 = ""
            actual_md_hashes: dict[str, str] = {}

            for info, norm_name, kind in validated_entries:
                if kind == "dir":
                    target_dir = (staging_dir / norm_name.rstrip("/")).resolve()
                    if not target_dir.is_relative_to(staging_dir.resolve()):
                        raise InvalidInputError("INVALID_ARCHIVE", "Archive directory escapes staging root")
                    target_dir.mkdir(parents=True, exist_ok=True)
                    continue

                if kind == "markdown" and len(actual_md_hashes) + 1 > self.max_backup_note_files:
                    raise InvalidInputError(
                        "INVALID_ARCHIVE",
                        f"Archive exceeds maximum of {self.max_backup_note_files} Markdown files",
                    )

                target_file = (staging_dir / norm_name).resolve()
                if not target_file.is_relative_to(staging_dir.resolve()):
                    raise InvalidInputError("INVALID_ARCHIVE", "Archive member escapes staging root")
                target_file.parent.mkdir(parents=True, exist_ok=True)

                hasher = hashlib.sha256()
                member_bytes = 0
                with zf.open(info, "r") as src_stream, open(target_file, "wb") as dst_file:
                    while True:
                        chunk = src_stream.read(STREAM_CHUNK_BYTES)
                        if not chunk:
                            break
                        total_extracted_bytes += len(chunk)
                        member_bytes += len(chunk)
                        if total_extracted_bytes > self.max_uncompressed_bytes:
                            raise PayloadTooLargeError(
                                f"Decompressed archive size exceeds limit of {self.max_uncompressed_bytes} bytes",
                                details={"max_uncompressed_bytes": self.max_uncompressed_bytes},
                            )
                        hasher.update(chunk)
                        dst_file.write(chunk)

                digest = hasher.hexdigest()
                if kind == "db":
                    actual_db_sha256 = digest
                    actual_db_plus_md_bytes += member_bytes
                elif kind == "markdown":
                    actual_md_hashes[norm_name] = digest
                    actual_db_plus_md_bytes += member_bytes
                    # Verify every staged Markdown file is valid UTF-8
                    try:
                        target_file.read_bytes().decode("utf-8")
                    except UnicodeDecodeError as exc:
                        raise InvalidInputError(
                            "INVALID_ARCHIVE",
                            f"Markdown file {norm_name!r} in archive is not valid UTF-8: {exc}",
                        ) from exc

        # Validate backup-manifest.json
        manifest_file = staging_dir / "backup-manifest.json"
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise InvalidInputError(
                "INVALID_ARCHIVE", f"Malformed backup-manifest.json: {exc}"
            ) from exc

        if not isinstance(manifest, dict):
            raise InvalidInputError(
                "INVALID_ARCHIVE", "backup-manifest.json must be a JSON object"
            )

        if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Unsupported backup format_version: {manifest.get('format_version')!r}",
            )

        if manifest.get("note_file_count") != len(actual_md_hashes):
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Manifest note_file_count ({manifest.get('note_file_count')}) does not match actual Markdown file count ({len(actual_md_hashes)})",
            )

        if manifest.get("total_uncompressed_bytes") != actual_db_plus_md_bytes:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Manifest total_uncompressed_bytes ({manifest.get('total_uncompressed_bytes')}) does not match actual bytes ({actual_db_plus_md_bytes})",
            )

        if manifest.get("db_sha256") != actual_db_sha256:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                "Manifest db_sha256 does not match devjournal.db digest",
            )

        manifest_files = manifest.get("files")
        if not isinstance(manifest_files, dict) or manifest_files != actual_md_hashes:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                "Manifest file list or SHA-256 digests do not match archive contents",
            )

        # Validate staged SQLite database header and integrity
        staged_db = staging_dir / "devjournal.db"
        with open(staged_db, "rb") as f:
            header = f.read(16)
        if header != b"SQLite format 3\x00":
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                "Staged devjournal.db does not have a valid SQLite 3 file header",
            )

        snapshot_settings: list[tuple[str, str, str]] = []
        snapshot_last_opened: dict[str, str] = {}
        try:
            conn = create_connection(staged_db)
            try:
                integrity = conn.execute("PRAGMA integrity_check;").fetchone()
                if integrity is None or str(integrity[0]).lower() != "ok":
                    raise InvalidInputError(
                        "INVALID_ARCHIVE",
                        f"Staged devjournal.db failed PRAGMA integrity_check: {integrity[0] if integrity else None}",
                    )

                tbl_rows = {
                    r["name"]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                if "notes" not in tbl_rows or "settings" not in tbl_rows:
                    raise InvalidInputError(
                        "INVALID_ARCHIVE",
                        "Staged devjournal.db is missing required 'notes' or 'settings' tables",
                    )

                for s_row in conn.execute(
                    "SELECT key, value_json, updated_at FROM settings"
                ).fetchall():
                    snapshot_settings.append(
                        (s_row["key"], s_row["value_json"], s_row["updated_at"])
                    )

                for n_row in conn.execute(
                    "SELECT id, last_opened_at FROM notes WHERE last_opened_at IS NOT NULL"
                ).fetchall():
                    snapshot_last_opened[n_row["id"]] = n_row["last_opened_at"]
            finally:
                conn.close()
        except InvalidInputError:
            raise
        except Exception as exc:
            raise InvalidInputError(
                "INVALID_ARCHIVE",
                f"Staged devjournal.db failed validation: {exc}",
            ) from exc

        return snapshot_settings, snapshot_last_opened

    def _populate_rollback_directory(self, rollback_dir: Path) -> None:
        """Create a complete local rollback copy of live devjournal.db and vault/."""
        rollback_vault = rollback_dir / "vault"
        rollback_vault_svc = VaultStorageService(rollback_vault)
        rollback_vault_svc.ensure_vault_structure()

        # Copy live SQLite database
        rollback_db = rollback_dir / "devjournal.db"
        with get_db_connection(self.db_path) as live_conn:
            rb_conn = sqlite3.connect(str(rollback_db))
            try:
                live_conn.backup(rb_conn)
            finally:
                rb_conn.close()

        with open(rollback_db, "r+b") as f:
            os.fsync(f.fileno())

        # Copy all live Markdown files into rollback_dir/vault
        for rel_path, _abs_path, _mtime in self.vault_storage.iter_markdown_files():
            text, _ = self.vault_storage.read_markdown(rel_path)
            rollback_vault_svc.write_markdown_atomic(rel_path, text)

        _fsync_dir_posix(rollback_dir)

    def _replace_vault_from_dir(self, source_vault_dir: Path) -> None:
        """Internal helper replacing live vault Markdown files from source_vault_dir."""
        self.vault_storage.ensure_vault_structure()
        source_vault_svc = VaultStorageService(source_vault_dir)
        source_files = source_vault_svc.iter_markdown_files()
        source_rel_set = {rel for rel, _, _ in source_files}

        # Remove live Markdown files absent from the snapshot
        for live_rel, live_abs, _mtime in self.vault_storage.iter_markdown_files():
            if live_rel not in source_rel_set:
                live_abs.unlink(missing_ok=True)

        # Write all staged Markdown files atomically into live vault
        for staged_rel, _staged_abs, _mtime in source_files:
            text, _ = source_vault_svc.read_markdown(staged_rel)
            self.vault_storage.write_markdown_atomic(staged_rel, text)

        for folder in CANONICAL_VAULT_FOLDERS:
            _fsync_dir_posix(self.vault_dir / folder)
        _fsync_dir_posix(self.vault_dir)

    def _apply_stage_4a_vault_replacement(self, staged_vault_dir: Path) -> None:
        """Stage 4a: Replace live vault Markdown files from staged_vault_dir."""
        self._replace_vault_from_dir(staged_vault_dir)

    def _apply_stage_4b_settings_replacement(
        self, snapshot_settings: list[tuple[str, str, str]]
    ) -> None:
        """Stage 4b: Replace all rows in settings table with snapshot_settings."""
        with get_db_transaction(self.db_path) as conn:
            conn.execute("DELETE FROM settings;")
            if snapshot_settings:
                conn.executemany(
                    "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?)",
                    snapshot_settings,
                )

    def _apply_stage_4c_full_reindex(self) -> ReindexResult:
        """Stage 4c: Rebuild SQLite notes, junctions, and FTS5 from the restored vault."""
        indexer = IndexerService(
            vault_storage=self.vault_storage, db_path=self.db_path
        )
        return indexer.full_reindex()

    def _apply_stage_4d_restore_last_opened(
        self, snapshot_last_opened: dict[str, str]
    ) -> None:
        """Stage 4d: Restore last_opened_at timestamps from the snapshot DB."""
        with get_db_transaction(self.db_path) as conn:
            conn.execute("UPDATE notes SET last_opened_at = NULL;")
            if snapshot_last_opened:
                conn.executemany(
                    "UPDATE notes SET last_opened_at = ? WHERE id = ?",
                    [(ts, nid) for nid, ts in snapshot_last_opened.items()],
                )

    def _rollback_from_directory(self, rollback_dir: Path) -> None:
        """Restore live vault/ and devjournal.db from rollback_dir and reconcile."""
        rollback_vault = rollback_dir / "vault"
        rollback_db = rollback_dir / "devjournal.db"
        if not rollback_vault.is_dir() or not rollback_db.is_file():
            raise RuntimeError(f"Rollback directory {rollback_dir} is incomplete")

        self._replace_vault_from_dir(rollback_vault)

        rb_conn = sqlite3.connect(str(rollback_db))
        try:
            with get_db_connection(self.db_path) as live_conn:
                rb_conn.backup(live_conn)
        finally:
            rb_conn.close()

        IndexerService(
            vault_storage=self.vault_storage, db_path=self.db_path
        ).reconcile_vault()

    def restore_from_stream(
        self, upload_stream: BinaryIO, *, drain_timeout: float = 30.0
    ) -> RestoreResponse:
        """Stream an uploaded backup .zip, validate it, drain active requests, and restore with journaled rollback."""
        maintenance_gate.check_can_begin_restore()
        self._ensure_dirs()

        start_ns = time.perf_counter_ns()
        op_id = uuid.uuid4().hex
        staging_dir = self.data_dir / f".restore-stage-{op_id}"
        rollback_dir = self.data_dir / f".restore-rollback-{op_id}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        uploaded_zip = staging_dir / "upload.zip"

        # Step 1 & Step 2: Stream upload and validate in staging_dir (outside maintenance gate & db_write_lock)
        try:
            total_uploaded = 0
            with open(uploaded_zip, "wb") as out_f:
                while True:
                    chunk = upload_stream.read(STREAM_CHUNK_BYTES)
                    if not chunk:
                        break
                    total_uploaded += len(chunk)
                    if total_uploaded > self.max_compressed_upload_bytes:
                        raise PayloadTooLargeError(
                            f"Uploaded backup archive exceeds maximum compressed size of {self.max_compressed_upload_bytes} bytes",
                            details={
                                "max_compressed_upload_bytes": self.max_compressed_upload_bytes
                            },
                        )
                    out_f.write(chunk)
                out_f.flush()

            snapshot_settings, snapshot_last_opened = (
                self._stage_and_validate_archive(uploaded_zip, staging_dir)
            )
            uploaded_zip.unlink(missing_ok=True)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        # Step 3: Close admission & wait for active request leases to drain BEFORE acquiring db_write_lock (P0-1)
        try:
            maintenance_gate.begin_maintenance_and_drain(timeout=drain_timeout)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

        journal_created = False
        rollback_failed = False
        try:
            with db_write_lock:
                if self.vault_storage.has_pending_move_journal():
                    self.vault_storage.recover_interrupted_moves(db_path=self.db_path)

                # Create pre-restore safety backup and local rollback directory
                safety_backup = self._create_backup_locked(safety_op_id=op_id)
                rollback_dir.mkdir(parents=True, exist_ok=True)
                self._populate_rollback_directory(rollback_dir)

                journal_payload = {
                    "operation_id": op_id,
                    "stage": "REPLACING_VAULT",
                    "started_at": _now_utc_iso(),
                    "safety_backup_filename": safety_backup.filename,
                    "rollback_dir": str(rollback_dir),
                    "staging_dir": str(staging_dir),
                }
                _write_json_atomic(self.journal_path, journal_payload)
                journal_created = True

                try:
                    # Stage 4a: Vault Replacement
                    self._apply_stage_4a_vault_replacement(staging_dir / "vault")

                    # Stage 4b: Settings Replacement
                    journal_payload["stage"] = "RESTORING_SETTINGS"
                    _write_json_atomic(self.journal_path, journal_payload)
                    self._apply_stage_4b_settings_replacement(snapshot_settings)

                    # Stage 4c: Full Reindex
                    journal_payload["stage"] = "REINDEXING"
                    _write_json_atomic(self.journal_path, journal_payload)
                    reindex_res = self._apply_stage_4c_full_reindex()

                    # Stage 4d: Restore last_opened_at
                    journal_payload["stage"] = "RESTORING_LAST_OPENED"
                    _write_json_atomic(self.journal_path, journal_payload)
                    self._apply_stage_4d_restore_last_opened(snapshot_last_opened)

                except Exception as restore_exc:
                    logger.error(
                        "Restore failed at stage %s (%s); initiating rollback",
                        journal_payload.get("stage"),
                        restore_exc,
                    )
                    journal_payload["stage"] = "ROLLING_BACK"
                    try:
                        _write_json_atomic(self.journal_path, journal_payload)
                    except Exception:
                        pass

                    try:
                        self._rollback_from_directory(rollback_dir)
                    except Exception as rollback_exc:
                        rollback_failed = True
                        logger.critical(
                            "CRITICAL: Restore rollback failed (%s). Retaining .restore-journal.json and %s",
                            rollback_exc,
                            rollback_dir,
                        )
                        maintenance_gate.mark_degraded(
                            f"Restore rollback failed: {rollback_exc}"
                        )
                        shutil.rmtree(staging_dir, ignore_errors=True)
                        raise rollback_exc from restore_exc

                    # Rollback succeeded: now safe to remove .restore-journal.json and temp dirs
                    self.journal_path.unlink(missing_ok=True)
                    _fsync_dir_posix(self.data_dir)
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    shutil.rmtree(rollback_dir, ignore_errors=True)
                    raise restore_exc

                # Commit: all 4 stages succeeded
                self.journal_path.unlink(missing_ok=True)
                _fsync_dir_posix(self.data_dir)
                shutil.rmtree(staging_dir, ignore_errors=True)
                shutil.rmtree(rollback_dir, ignore_errors=True)

                duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
                return RestoreResponse(
                    status="ok",
                    indexed=reindex_res.indexed,
                    safety_backup_filename=safety_backup.filename,
                    duration_ms=duration_ms,
                )
        finally:
            if not rollback_failed:
                if not journal_created:
                    shutil.rmtree(staging_dir, ignore_errors=True)
                    shutil.rmtree(rollback_dir, ignore_errors=True)
                maintenance_gate.end_maintenance()

    def recover_interrupted_restore_if_any(self) -> bool:
        """Fail-closed startup recovery for interrupted restores (.restore-journal.json)."""
        if not self.journal_path.exists():
            return False

        logger.warning(
            "Detected interrupted restore journal at %s; starting recovery",
            self.journal_path,
        )
        with db_write_lock:
            try:
                journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
                if not isinstance(journal, dict):
                    raise RuntimeError("Corrupt .restore-journal.json: not a JSON object")

                rollback_dir_str = journal.get("rollback_dir")
                staging_dir_str = journal.get("staging_dir")
                safety_filename = journal.get("safety_backup_filename")

                rollback_dir = Path(rollback_dir_str) if rollback_dir_str else None
                staging_dir = Path(staging_dir_str) if staging_dir_str else None

                recovered = False
                if (
                    rollback_dir is not None
                    and (rollback_dir / "vault").is_dir()
                    and (rollback_dir / "devjournal.db").is_file()
                ):
                    self._rollback_from_directory(rollback_dir)
                    recovered = True
                elif safety_filename:
                    safety_zip = self.backups_dir / safety_filename
                    if safety_zip.is_file():
                        temp_extract = self.data_dir / f".startup-recover-{uuid.uuid4().hex}"
                        try:
                            snap_settings, snap_opened = self._stage_and_validate_archive(
                                safety_zip, temp_extract
                            )
                            self._apply_stage_4a_vault_replacement(
                                temp_extract / "vault"
                            )
                            self._apply_stage_4b_settings_replacement(snap_settings)
                            self._apply_stage_4c_full_reindex()
                            self._apply_stage_4d_restore_last_opened(snap_opened)
                            recovered = True
                        finally:
                            shutil.rmtree(temp_extract, ignore_errors=True)

                if not recovered:
                    raise RuntimeError(
                        "Neither rollback_dir nor safety_backup_filename is usable for startup restore recovery"
                    )

                self._apply_stage_4c_full_reindex()

                # Only unlink journal and remove directories AFTER recovery and reindex succeed
                self.journal_path.unlink(missing_ok=True)
                _fsync_dir_posix(self.data_dir)
                if staging_dir and staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                if rollback_dir and rollback_dir.exists():
                    shutil.rmtree(rollback_dir, ignore_errors=True)

                return True
            except Exception as exc:
                logger.critical(
                    "CRITICAL: Startup restore recovery failed (%s). Retaining .restore-journal.json and aborting startup.",
                    exc,
                )
                maintenance_gate.mark_degraded(
                    f"Startup restore recovery failed: {exc}"
                )
                raise RuntimeError(
                    f"Application startup aborted due to unrecoverable interrupted restore: {exc}"
                ) from exc
