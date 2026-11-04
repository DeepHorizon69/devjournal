from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from app.config import settings
from app.db.connection import RestoreInProgressError, db_write_lock, get_db_transaction, maintenance_gate

logger = logging.getLogger(__name__)

CANONICAL_VAULT_FOLDERS: tuple[str, ...] = (
    "00-Inbox",
    "10-Notes",
    "20-Projects",
    "30-Experiments",
    "40-Troubleshooting",
    "50-Snippets",
    "90-Daily",
    "99-Trash",
)

NOTE_TYPE_TO_FOLDER: dict[str, str] = {
    "note": "10-Notes",
    "project": "20-Projects",
    "experiment": "30-Experiments",
    "troubleshooting": "40-Troubleshooting",
    "snippet": "50-Snippets",
    "daily": "90-Daily",
}

TRASH_FOLDER = "99-Trash"
INBOX_FOLDER = "00-Inbox"

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_DAILY_TITLE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Set of resolved vault_dir paths known to have pending .move-journal-*.json files
_PENDING_MOVE_VAULTS: set[Path] = set()


class VaultError(Exception):
    """Base exception for vault storage operations."""


class PathTraversalError(VaultError):
    """Raised when a relative path attempts to escape the canonical vault folders."""


class NoteFileNotFoundError(VaultError):
    """Raised when a requested Markdown note file does not exist on disk."""


class NoteFileExistsError(VaultError):
    """Raised when a move destination already exists and overwrite is not permitted."""


class InvalidTrashOperationError(VaultError):
    """Raised when a trash/restore/permanent-delete operation violates folder invariants."""


class InvalidEncodingError(VaultError):
    """Raised when a Markdown file on disk is not valid UTF-8."""


class NoteNotFoundError(VaultError):
    """Raised when a requested note ID does not exist in SQLite or on disk."""

    def __init__(self, note_id: str) -> None:
        self.note_id = note_id
        super().__init__(f"Note not found: {note_id}")


class InvalidInputError(VaultError):
    """Raised when an API request contains invalid parameters, dates, or archive content."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class PayloadTooLargeError(VaultError):
    """Raised when an uploaded file or backup exceeds configured byte/entry limits."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = "PAYLOAD_TOO_LARGE"
        self.message = message
        self.details = details or {}
        super().__init__(message)


def slugify_title(title: str, fallback_id: str | None = None) -> str:
    """Convert a note title into a filesystem-safe lowercase ASCII slug."""
    normalized = (
        unicodedata.normalize("NFKD", title or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = _NON_ALNUM_RE.sub("-", normalized).strip("-")
    if len(slug) > 80:
        slug = slug[:80].rstrip("-")
    if not slug:
        if fallback_id:
            return f"untitled-{fallback_id[:8]}"
        return "untitled"
    return slug


def _fsync_dir_posix(dir_path: Path) -> None:
    """Sync directory metadata on POSIX platforms."""
    if os.name != "posix":
        return
    try:
        dir_fd = os.open(str(dir_path), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def _normalize_lf(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _sha256_lf(content: str) -> str:
    return hashlib.sha256(_normalize_lf(content).encode("utf-8")).hexdigest()


def _merge_frontmatter_if_missing(src_text: str, new_content: str) -> str:
    """If src_text has a YAML frontmatter block and new_content does not, preserve src_text's frontmatter."""
    src_lf = _normalize_lf(src_text)
    new_lf = _normalize_lf(new_content)
    if new_lf.startswith("---\n") or new_lf == "---":
        return new_lf
    if src_lf.startswith("---\n"):
        close_idx = src_lf.find("\n---\n", 3)
        if close_idx != -1:
            return src_lf[: close_idx + 5] + new_lf
    return new_lf


class VaultStorageService:
    """Manages canonical Markdown note files inside the 8 vault subdirectories."""

    def __init__(self, vault_dir: Path | None = None, db_path: Path | None = None) -> None:
        self.vault_dir = (Path(vault_dir) if vault_dir is not None else settings.vault_dir).resolve()
        self._db_path = Path(db_path) if db_path is not None else None
        self._in_recovery = False

    def ensure_vault_structure(self) -> None:
        """Create vault_dir and all 8 canonical vault folders if they do not exist."""
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        for folder in CANONICAL_VAULT_FOLDERS:
            (self.vault_dir / folder).mkdir(parents=True, exist_ok=True)

    def has_pending_move_journal(self) -> bool:
        """Check whether this vault has any pending .move-journal-*.json files."""
        if self.vault_dir in _PENDING_MOVE_VAULTS:
            return True
        if not self.vault_dir.exists():
            return False
        try:
            for entry in os.scandir(self.vault_dir):
                if entry.name.startswith(".move-journal-") and entry.name.endswith(".json"):
                    _PENDING_MOVE_VAULTS.add(self.vault_dir)
                    return True
        except OSError:
            pass
        return False

    def _ensure_moves_recovered(self) -> None:
        """Runtime barrier: automatically recover any interrupted move before accessing the vault."""
        if self._in_recovery:
            return
        if self.has_pending_move_journal():
            self.recover_interrupted_moves(db_path=self._db_path)

    def resolve_safe_path(self, rel_path: str | Path) -> Path:
        """Resolve a vault-relative path safely inside one of the 8 canonical folders."""
        if rel_path is None:
            raise PathTraversalError("Vault path cannot be None")

        raw_str = str(rel_path)
        if not raw_str or not raw_str.strip() or "\x00" in raw_str:
            raise PathTraversalError(f"Unsafe vault path: {rel_path!r}")

        if isinstance(rel_path, Path) and rel_path.is_absolute():
            raise PathTraversalError(f"Absolute path not allowed: {rel_path}")

        if raw_str.startswith(("/", "\\")) or _WINDOWS_DRIVE_RE.match(raw_str):
            raise PathTraversalError(f"Absolute or drive-prefixed path not allowed: {rel_path}")

        norm = raw_str.replace("\\", "/")
        raw_segments = [seg for seg in norm.split("/") if seg != ""]
        if any(seg in (".", "..") for seg in raw_segments):
            raise PathTraversalError(f"Relative path traversal segment not allowed: {rel_path}")

        pure = PurePosixPath(norm)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or len(pure.parts) < 2
            or pure.parts[0] not in CANONICAL_VAULT_FOLDERS
        ):
            raise PathTraversalError(f"Unsafe vault path: {rel_path}")

        if not self.vault_dir.is_relative_to(self.vault_dir):
            raise PathTraversalError("Invalid vault root")

        # Check intermediate components for symlink escapes
        current = self.vault_dir
        if current.is_symlink():
            if not current.resolve().is_relative_to(self.vault_dir):
                raise PathTraversalError(f"Symlink escape on vault root: {rel_path}")

        for part in pure.parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if current.is_symlink():
                    resolved_target = current.resolve()
                    if not resolved_target.is_relative_to(self.vault_dir):
                        raise PathTraversalError(f"Symlink escape detected in path: {rel_path}")

        candidate = self.vault_dir.joinpath(*pure.parts)
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.vault_dir):
            raise PathTraversalError(f"Unsafe vault path escaping vault root: {rel_path}")

        canonical_folder_root = (self.vault_dir / pure.parts[0]).resolve()
        if not resolved.is_relative_to(canonical_folder_root) or resolved == canonical_folder_root:
            raise PathTraversalError(f"Unsafe vault path outside canonical folder: {rel_path}")

        if resolved.suffix.lower() != ".md":
            raise PathTraversalError("Vault note path must end with .md")

        return resolved

    def to_rel_path(self, abs_path: Path) -> str:
        """Convert an absolute path inside vault_dir to a POSIX relative path."""
        resolved = Path(abs_path).resolve()
        if not resolved.is_relative_to(self.vault_dir):
            raise PathTraversalError(f"Path {abs_path} is outside vault_dir {self.vault_dir}")
        rel_posix = resolved.relative_to(self.vault_dir).as_posix()
        pure = PurePosixPath(rel_posix)
        if len(pure.parts) < 2 or pure.parts[0] not in CANONICAL_VAULT_FOLDERS:
            raise PathTraversalError(f"Path {abs_path} is not inside a canonical vault folder")
        return rel_posix

    def generate_unique_rel_path(
        self,
        folder: str,
        title: str,
        note_id: str,
        existing_rel_path: str | None = None,
    ) -> str:
        """Generate a collision-free POSIX relative path inside a canonical vault folder."""
        if folder not in CANONICAL_VAULT_FOLDERS:
            raise PathTraversalError(f"Invalid canonical vault folder: {folder}")

        clean_title = (title or "").strip()
        if folder == "90-Daily" and _DAILY_TITLE_RE.match(clean_title):
            slug = clean_title
        else:
            slug = slugify_title(clean_title, fallback_id=note_id)

        existing_norm = (
            PurePosixPath(existing_rel_path.replace("\\", "/")).as_posix()
            if existing_rel_path
            else None
        )

        candidate_1 = f"{folder}/{slug}.md"
        if existing_norm == candidate_1 or not self.resolve_safe_path(candidate_1).exists():
            return candidate_1

        short_id = (note_id or "note")[:8]
        candidate_2 = f"{folder}/{slug}-{short_id}.md"
        if existing_norm == candidate_2 or not self.resolve_safe_path(candidate_2).exists():
            return candidate_2

        counter = 2
        while True:
            candidate_n = f"{folder}/{slug}-{short_id}-{counter}.md"
            if existing_norm == candidate_n or not self.resolve_safe_path(candidate_n).exists():
                return candidate_n
            counter += 1

    def _write_markdown_atomic_internal(self, rel_path: str, content: str) -> tuple[Path, float]:
        """Internal atomic Markdown writer via sibling .tmp-<uuid>.md and os.replace."""
        target_path = self.resolve_safe_path(rel_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        normalized = _normalize_lf(content)
        temp_path = target_path.parent / f".tmp-{uuid.uuid4().hex}.md"

        try:
            with open(temp_path, "wb") as f:
                f.write(normalized.encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, target_path)
            _fsync_dir_posix(target_path.parent)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

        return target_path, target_path.stat().st_mtime

    def write_markdown_atomic(self, rel_path: str, content: str) -> tuple[Path, float]:
        """Atomically write LF-normalized UTF-8 Markdown via sibling .tmp-<uuid>.md and os.replace."""
        self._ensure_moves_recovered()
        return self._write_markdown_atomic_internal(rel_path, content)

    def _read_markdown_internal(self, rel_path: str) -> tuple[str, float]:
        """Internal strict UTF-8 Markdown reader."""
        target_path = self.resolve_safe_path(rel_path)
        if not target_path.is_file():
            raise NoteFileNotFoundError(rel_path)

        raw_bytes = target_path.read_bytes()
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidEncodingError(
                f"File {rel_path} is not valid UTF-8: {exc}"
            ) from exc

        return text, target_path.stat().st_mtime

    def read_markdown(self, rel_path: str) -> tuple[str, float]:
        """Read a Markdown note from disk with strict UTF-8 decoding."""
        self._ensure_moves_recovered()
        return self._read_markdown_internal(rel_path)

    def _sync_recovered_note_to_db(
        self,
        rel_path: str,
        raw_content: str,
        mtime: float,
        db_path: Path | None,
        *,
        sync_db: bool = True,
    ) -> None:
        """Synchronize a move-recovered note into SQLite if explicitly configured with db_path."""
        if not sync_db:
            return
        target_db = Path(db_path) if db_path is not None else self._db_path
        if target_db is None or not target_db.is_file():
            return

        try:
            from app.repositories.notes_repo import NotesRepository
            from app.services.frontmatter_svc import parse_markdown_note

            parsed = parse_markdown_note(raw_content, rel_path=rel_path, file_mtime=mtime)
            repo = NotesRepository()
            with get_db_transaction(target_db) as conn:
                row = conn.execute(
                    "SELECT count(*) AS cnt FROM sqlite_master WHERE type='table' AND name='notes'"
                ).fetchone()
                if row is not None and int(row["cnt"]) > 0:
                    repo.upsert_parsed_note(conn, parsed)
        except Exception as exc:
            logger.warning("Deferred SQLite sync during move journal recovery for %s: %s", rel_path, exc)

    def recover_interrupted_moves(
        self, db_path: Path | None = None, *, sync_db: bool = True
    ) -> int:
        """Recover any interrupted move_note(updated_content=...) operations from .move-journal-*.json."""
        if self._in_recovery or not self.vault_dir.exists():
            return 0

        journal_files = sorted(self.vault_dir.glob(".move-journal-*.json"))
        if not journal_files:
            _PENDING_MOVE_VAULTS.discard(self.vault_dir)
            return 0

        recovered_count = 0
        self._in_recovery = True
        try:
            with db_write_lock:
                for journal_path in journal_files:
                    if not journal_path.exists():
                        continue
                    try:
                        if journal_path.is_symlink() or journal_path.resolve().parent != self.vault_dir:
                            raise PathTraversalError(f"Unsafe move journal path: {journal_path}")

                        raw_json = journal_path.read_text(encoding="utf-8")
                        journal_data = json.loads(raw_json)
                        if not isinstance(journal_data, dict):
                            raise VaultError("Move journal must be a JSON object")

                        src_rel_path = journal_data.get("src_rel_path")
                        dest_rel_path = journal_data.get("dest_rel_path")
                        staged_filename = journal_data.get("staged_filename")
                        staged_sha256 = journal_data.get("staged_sha256")
                        src_original_sha256 = journal_data.get("src_original_sha256")

                        if not all(
                            isinstance(val, str) and val.strip()
                            for val in (
                                src_rel_path,
                                dest_rel_path,
                                staged_filename,
                                staged_sha256,
                                src_original_sha256,
                            )
                        ):
                            raise VaultError("Move journal missing required string fields")

                        # 1. Validate src and dest paths via resolve_safe_path
                        src_path = self.resolve_safe_path(src_rel_path)
                        dest_path = self.resolve_safe_path(dest_rel_path)

                        # 2. Validate staged_filename inside vault_dir
                        if (
                            "/" in staged_filename
                            or "\\" in staged_filename
                            or ".." in staged_filename
                            or not staged_filename.startswith(".move-staged-")
                        ):
                            raise PathTraversalError(f"Invalid staged_filename in move journal: {staged_filename!r}")

                        staged_path = self.vault_dir / staged_filename
                        if (
                            staged_path.is_symlink()
                            or not staged_path.is_file()
                            or staged_path.resolve().parent != self.vault_dir
                        ):
                            raise VaultError(f"Missing or unsafe staged file: {staged_filename}")

                        staged_text = staged_path.read_bytes().decode("utf-8")
                        if _sha256_lf(staged_text) != staged_sha256:
                            raise VaultError("Staged move content SHA-256 mismatch")

                        src_exists = src_path.is_file()
                        dest_exists = dest_path.is_file()

                        # Case 1: Rename did not happen yet (src_path exists, dest_path does not)
                        if src_exists and not dest_exists:
                            staged_path.unlink(missing_ok=True)
                            journal_path.unlink(missing_ok=True)
                            _fsync_dir_posix(self.vault_dir)
                            recovered_count += 1
                            continue

                        # Case 2: Rename happened, destination awaits updated content (src missing, dest exists)
                        if not src_exists and dest_exists:
                            dest_text, _ = self._read_markdown_internal(dest_rel_path)
                            dest_hash = _sha256_lf(dest_text)
                            if dest_hash in (src_original_sha256, staged_sha256):
                                # Destination is the moved note: roll forward
                                _, mtime = self._write_markdown_atomic_internal(dest_rel_path, staged_text)
                                self._sync_recovered_note_to_db(
                                    dest_rel_path, staged_text, mtime, db_path, sync_db=sync_db
                                )
                            else:
                                # Destination is now occupied by an unrelated file! Never overwrite dest_path.
                                _, mtime = self._write_markdown_atomic_internal(src_rel_path, staged_text)
                                self._sync_recovered_note_to_db(
                                    src_rel_path, staged_text, mtime, db_path, sync_db=sync_db
                                )

                            staged_path.unlink(missing_ok=True)
                            journal_path.unlink(missing_ok=True)
                            _fsync_dir_posix(self.vault_dir)
                            recovered_count += 1
                            continue

                        # Case 3: Both src_path and dest_path exist
                        if src_exists and dest_exists:
                            src_text, _ = self._read_markdown_internal(src_rel_path)
                            dest_text, _ = self._read_markdown_internal(dest_rel_path)
                            src_hash = _sha256_lf(src_text)
                            dest_hash = _sha256_lf(dest_text)

                            if dest_hash == staged_sha256 and src_hash == src_original_sha256:
                                src_path.unlink(missing_ok=True)
                                _fsync_dir_posix(src_path.parent)
                                self._sync_recovered_note_to_db(
                                    dest_rel_path,
                                    dest_text,
                                    dest_path.stat().st_mtime,
                                    db_path,
                                    sync_db=sync_db,
                                )
                                staged_path.unlink(missing_ok=True)
                                journal_path.unlink(missing_ok=True)
                                _fsync_dir_posix(self.vault_dir)
                                recovered_count += 1
                                continue
                            elif src_hash == src_original_sha256 and dest_hash != staged_sha256:
                                # dest_path is an unrelated file; roll back cleanly leaving both intact
                                staged_path.unlink(missing_ok=True)
                                journal_path.unlink(missing_ok=True)
                                _fsync_dir_posix(self.vault_dir)
                                recovered_count += 1
                                continue
                            else:
                                raise VaultError(
                                    f"Ambiguous move journal state between {src_rel_path} and {dest_rel_path}"
                                )

                        # Case 4: Neither exists (materialize staged content at dest_rel_path)
                        _, mtime = self._write_markdown_atomic_internal(dest_rel_path, staged_text)
                        self._sync_recovered_note_to_db(
                            dest_rel_path, staged_text, mtime, db_path, sync_db=sync_db
                        )
                        staged_path.unlink(missing_ok=True)
                        journal_path.unlink(missing_ok=True)
                        _fsync_dir_posix(self.vault_dir)
                        recovered_count += 1

                    except Exception as exc:
                        logger.critical(
                            "Failed to recover interrupted move journal %s: %s",
                            journal_path,
                            exc,
                        )
                        maintenance_gate.mark_degraded(f"Move journal recovery failed: {exc}")
                        raise RestoreInProgressError(
                            f"System entered protected degraded state due to move journal recovery failure: {exc}"
                        ) from exc

                remaining = list(self.vault_dir.glob(".move-journal-*.json"))
                if not remaining:
                    _PENDING_MOVE_VAULTS.discard(self.vault_dir)
        finally:
            self._in_recovery = False

        return recovered_count

    def move_note(
        self,
        src_rel_path: str,
        dest_rel_path: str,
        updated_content: str | None = None,
        *,
        allow_overwrite: bool = False,
    ) -> tuple[Path, float]:
        """Crash-safe note move: staged content + move journal, atomic os.replace first, then atomic destination write."""
        self._ensure_moves_recovered()

        src_path = self.resolve_safe_path(src_rel_path)
        dest_path = self.resolve_safe_path(dest_rel_path)

        if not src_path.is_file():
            raise NoteFileNotFoundError(src_rel_path)

        if src_path != dest_path and dest_path.exists() and not allow_overwrite:
            raise NoteFileExistsError(f"Destination file already exists: {dest_rel_path}")

        norm_src_rel = self.to_rel_path(src_path)
        norm_dest_rel = self.to_rel_path(dest_path)

        if src_path == dest_path:
            if updated_content is not None:
                return self.write_markdown_atomic(norm_dest_rel, updated_content)
            return dest_path, dest_path.stat().st_mtime

        if updated_content is None:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src_path, dest_path)
            _fsync_dir_posix(src_path.parent)
            if dest_path.parent != src_path.parent:
                _fsync_dir_posix(dest_path.parent)
            return dest_path, dest_path.stat().st_mtime

        # Journaled move + content update (P0-2)
        src_text, _ = self._read_markdown_internal(norm_src_rel)
        src_original_sha256 = _sha256_lf(src_text)
        normalized_updated = _normalize_lf(updated_content)
        staged_sha256 = _sha256_lf(normalized_updated)

        op_id = uuid.uuid4().hex
        staged_filename = f".move-staged-{op_id}.tmp"
        staged_path = self.vault_dir / staged_filename
        journal_path = self.vault_dir / f".move-journal-{op_id}.json"
        temp_journal_path = self.vault_dir / f".tmp-move-journal-{op_id}.json"

        try:
            # 1. Write staged content file and fsync
            with open(staged_path, "wb") as sf:
                sf.write(normalized_updated.encode("utf-8"))
                sf.flush()
                os.fsync(sf.fileno())

            # 2. Atomically write move journal and fsync
            journal_payload = {
                "op_id": op_id,
                "src_rel_path": norm_src_rel,
                "dest_rel_path": norm_dest_rel,
                "staged_filename": staged_filename,
                "staged_sha256": staged_sha256,
                "src_original_sha256": src_original_sha256,
            }
            with open(temp_journal_path, "wb") as jf:
                jf.write(json.dumps(journal_payload).encode("utf-8"))
                jf.flush()
                os.fsync(jf.fileno())

            os.replace(temp_journal_path, journal_path)
            _fsync_dir_posix(self.vault_dir)
            _PENDING_MOVE_VAULTS.add(self.vault_dir)
        except Exception:
            temp_journal_path.unlink(missing_ok=True)
            staged_path.unlink(missing_ok=True)
            journal_path.unlink(missing_ok=True)
            raise

        # 3. Atomic filesystem rename first so source and destination never coexist as duplicates
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src_path, dest_path)
            _fsync_dir_posix(src_path.parent)
            if dest_path.parent != src_path.parent:
                _fsync_dir_posix(dest_path.parent)
        except Exception:
            # Rename did not happen; clean up journal & staged file immediately
            if src_path.is_file() and not dest_path.exists():
                staged_path.unlink(missing_ok=True)
                journal_path.unlink(missing_ok=True)
                if not list(self.vault_dir.glob(".move-journal-*.json")):
                    _PENDING_MOVE_VAULTS.discard(self.vault_dir)
            raise

        # 4. Atomic metadata/content update at destination
        dest_path, mtime = self.write_markdown_atomic(norm_dest_rel, normalized_updated)

        # 5. Clean up staged file and move journal upon successful destination write
        staged_path.unlink(missing_ok=True)
        journal_path.unlink(missing_ok=True)
        _fsync_dir_posix(self.vault_dir)
        if not list(self.vault_dir.glob(".move-journal-*.json")):
            _PENDING_MOVE_VAULTS.discard(self.vault_dir)

        return dest_path, mtime

    def move_to_trash(
        self,
        rel_path: str,
        note_id: str,
        trashed_content: str,
    ) -> tuple[str, Path, float]:
        """Move an active note into 99-Trash/ with collision avoidance and crash-safe ordering."""
        self._ensure_moves_recovered()

        norm_rel = PurePosixPath(rel_path.replace("\\", "/"))
        if len(norm_rel.parts) > 0 and norm_rel.parts[0] == TRASH_FOLDER:
            raise InvalidTrashOperationError(
                f"Note is already in {TRASH_FOLDER}: {rel_path}"
            )

        src_path = self.resolve_safe_path(rel_path)
        if not src_path.is_file():
            raise NoteFileNotFoundError(rel_path)

        src_text, _ = self._read_markdown_internal(rel_path)
        effective_content = _merge_frontmatter_if_missing(src_text, trashed_content)

        stem = src_path.stem
        short_id = (note_id or "note")[:8]

        candidate_1 = f"{TRASH_FOLDER}/{stem}.md"
        if not self.resolve_safe_path(candidate_1).exists():
            trash_rel_path = candidate_1
        else:
            candidate_2 = f"{TRASH_FOLDER}/{stem}-{short_id}.md"
            if not self.resolve_safe_path(candidate_2).exists():
                trash_rel_path = candidate_2
            else:
                i = 2
                while True:
                    candidate_n = f"{TRASH_FOLDER}/{stem}-{short_id}-{i}.md"
                    if not self.resolve_safe_path(candidate_n).exists():
                        trash_rel_path = candidate_n
                        break
                    i += 1

        dest_path, mtime = self.move_note(
            rel_path,
            trash_rel_path,
            updated_content=effective_content,
            allow_overwrite=False,
        )
        return trash_rel_path, dest_path, mtime

    def restore_from_trash(
        self,
        trash_rel_path: str,
        original_rel_path: str | None,
        fallback_folder: str,
        title: str,
        note_id: str,
        restored_content: str,
    ) -> tuple[str, Path, float]:
        """Restore a note from 99-Trash/ to its original_rel_path or a collision-free fallback path."""
        self._ensure_moves_recovered()

        norm_trash = PurePosixPath(trash_rel_path.replace("\\", "/"))
        if len(norm_trash.parts) == 0 or norm_trash.parts[0] != TRASH_FOLDER:
            raise InvalidTrashOperationError(
                f"Note is not in {TRASH_FOLDER}: {trash_rel_path}"
            )

        src_path = self.resolve_safe_path(trash_rel_path)
        if not src_path.is_file():
            raise NoteFileNotFoundError(trash_rel_path)

        src_text, _ = self._read_markdown_internal(trash_rel_path)
        effective_content = _merge_frontmatter_if_missing(src_text, restored_content)

        target_rel_path: str | None = None
        if original_rel_path and original_rel_path.strip():
            try:
                orig_resolved = self.resolve_safe_path(original_rel_path)
                orig_posix = self.to_rel_path(orig_resolved)
                orig_folder = PurePosixPath(orig_posix).parts[0]
                if orig_folder != TRASH_FOLDER and not orig_resolved.exists():
                    target_rel_path = orig_posix
            except PathTraversalError:
                target_rel_path = None

        if target_rel_path is None:
            valid_fallback = (
                fallback_folder
                if (fallback_folder in CANONICAL_VAULT_FOLDERS and fallback_folder != TRASH_FOLDER)
                else "10-Notes"
            )
            target_rel_path = self.generate_unique_rel_path(
                valid_fallback, title, note_id
            )

        dest_path, mtime = self.move_note(
            trash_rel_path,
            target_rel_path,
            updated_content=effective_content,
            allow_overwrite=False,
        )
        return target_rel_path, dest_path, mtime

    def delete_permanently(
        self,
        rel_path: str,
        *,
        allow_non_trash: bool = False,
    ) -> None:
        """Permanently unlink a note file from disk (restricted to 99-Trash by default)."""
        self._ensure_moves_recovered()

        target_path = self.resolve_safe_path(rel_path)
        rel_posix = self.to_rel_path(target_path)

        if not allow_non_trash and PurePosixPath(rel_posix).parts[0] != TRASH_FOLDER:
            raise InvalidTrashOperationError(
                f"Permanent deletion is restricted to notes in {TRASH_FOLDER}: {rel_path}"
            )

        if not target_path.is_file():
            raise NoteFileNotFoundError(rel_path)

        target_path.unlink()

    def iter_markdown_files(self) -> list[tuple[str, Path, float]]:
        """Walk the 8 canonical vault folders and return sorted (rel_path, abs_path, mtime)."""
        self._ensure_moves_recovered()

        results: list[tuple[str, Path, float]] = []

        for folder in CANONICAL_VAULT_FOLDERS:
            folder_path = self.vault_dir / folder
            if not folder_path.exists() or not folder_path.is_dir() or folder_path.is_symlink():
                continue

            for root, dirnames, filenames in os.walk(folder_path, followlinks=False):
                root_path = Path(root)
                # Prune hidden directories and symlinks in-place
                dirnames[:] = sorted(
                    d
                    for d in dirnames
                    if not d.startswith(".") and not (root_path / d).is_symlink()
                )

                for fname in sorted(filenames):
                    if fname.startswith(".") or not fname.lower().endswith(".md"):
                        continue
                    file_path = root_path / fname
                    if file_path.is_symlink() or not file_path.is_file():
                        continue
                    try:
                        resolved_file = file_path.resolve()
                        if not resolved_file.is_relative_to(self.vault_dir):
                            continue
                        rel_posix = resolved_file.relative_to(self.vault_dir).as_posix()
                        mtime = resolved_file.stat().st_mtime
                        results.append((rel_posix, resolved_file, mtime))
                    except OSError:
                        continue

        results.sort(key=lambda item: item[0])
        return results
