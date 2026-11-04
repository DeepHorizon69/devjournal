from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

# Single-worker in-process write lock coordinating SQLite write transactions,
# startup vault reconciliation, and full reindex runs.
db_write_lock = threading.RLock()


class RestoreInProgressError(Exception):
    """Raised when an API operation is rejected because a restore or recovery is in progress or degraded."""

    def __init__(
        self,
        message: str = "System restore is currently in progress. Please retry shortly.",
        *,
        code: str = "RESTORE_IN_PROGRESS",
    ) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class MaintenanceGate:
    """Thread-safe request-admission and active-request draining gate for snapshot restore and recovery."""

    def __init__(self) -> None:
        self._cond = threading.Condition(threading.Lock())
        self._active_leases: int = 0
        self._maintenance_closing: bool = False
        self._restore_in_progress: bool = False
        self._degraded_reason: str | None = None

    @property
    def active_leases(self) -> int:
        with self._cond:
            return self._active_leases

    @property
    def is_restore_in_progress(self) -> bool:
        with self._cond:
            return self._restore_in_progress

    @property
    def is_degraded(self) -> bool:
        with self._cond:
            return self._degraded_reason is not None

    @property
    def degraded_reason(self) -> str | None:
        with self._cond:
            return self._degraded_reason

    @property
    def is_blocked(self) -> bool:
        with self._cond:
            return (
                self._maintenance_closing
                or self._restore_in_progress
                or self._degraded_reason is not None
            )

    @contextmanager
    def acquire_request_lease(self) -> Iterator[None]:
        """Acquire a lease for an in-flight API data request, or raise RestoreInProgressError if maintenance is active."""
        with self._cond:
            if (
                self._maintenance_closing
                or self._restore_in_progress
                or self._degraded_reason is not None
            ):
                msg = (
                    f"System is in protected maintenance/degraded state: {self._degraded_reason}"
                    if self._degraded_reason
                    else "System restore is currently in progress. Please retry shortly."
                )
                raise RestoreInProgressError(msg)
            self._active_leases += 1

        try:
            yield
        finally:
            with self._cond:
                self._active_leases = max(0, self._active_leases - 1)
                if self._active_leases == 0:
                    self._cond.notify_all()

    def check_can_begin_restore(self) -> None:
        """Verify no other restore or degraded state is currently active."""
        with self._cond:
            if (
                self._maintenance_closing
                or self._restore_in_progress
                or self._degraded_reason is not None
            ):
                msg = (
                    f"System is in protected maintenance/degraded state: {self._degraded_reason}"
                    if self._degraded_reason
                    else "Another system restore is already in progress."
                )
                raise RestoreInProgressError(msg)

    def begin_maintenance_and_drain(self, timeout: float = 30.0) -> None:
        """Close admission to new requests and wait until all active request leases have drained.

        Must be called BEFORE acquiring db_write_lock so in-flight requests can finish without deadlocking.
        """
        with self._cond:
            if (
                self._maintenance_closing
                or self._restore_in_progress
                or self._degraded_reason is not None
            ):
                msg = (
                    f"System is in protected maintenance/degraded state: {self._degraded_reason}"
                    if self._degraded_reason
                    else "Another system restore is already in progress."
                )
                raise RestoreInProgressError(msg)

            self._maintenance_closing = True
            self._restore_in_progress = True

            drained = self._cond.wait_for(
                lambda: self._active_leases == 0, timeout=timeout
            )
            if not drained:
                self._maintenance_closing = False
                self._restore_in_progress = False
                self._cond.notify_all()
                raise RestoreInProgressError(
                    "Timed out waiting for active requests to drain before restore."
                )

    def end_maintenance(self) -> None:
        """Release maintenance mode after a successful restore or successful rollback."""
        with self._cond:
            if self._degraded_reason is None:
                self._maintenance_closing = False
            self._restore_in_progress = False
            self._cond.notify_all()

    def mark_degraded(self, reason: str) -> None:
        """Lock the gate in a protected degraded state when rollback or journal recovery fails."""
        with self._cond:
            self._degraded_reason = reason
            self._maintenance_closing = True
            self._restore_in_progress = False
            self._cond.notify_all()

    def reset_for_testing(self) -> None:
        """Reset all gate flags (used by test fixtures)."""
        with self._cond:
            self._active_leases = 0
            self._maintenance_closing = False
            self._restore_in_progress = False
            self._degraded_reason = None
            self._cond.notify_all()


maintenance_gate = MaintenanceGate()


def create_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Create a configured SQLite connection with per-connection pragmas.

    Note: PRAGMA journal_mode = WAL is persistent at the database file level
    and is initialized once in init_db() rather than on every connection checkout.
    """
    target_path = Path(db_path) if db_path is not None else settings.db_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path), timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextmanager
def get_db_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a configured SQLite connection and closing it on exit."""
    conn = create_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_transaction(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager acquiring db_write_lock and opening an immediate write transaction."""
    with db_write_lock:
        with get_db_connection(db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise


def init_db(db_path: Path | None = None) -> None:
    """Initialize SQLite WAL mode, execute idempotent schema DDL, and verify FTS5 support."""
    schema_sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

    with db_write_lock:
        with get_db_connection(db_path) as conn:
            mode_row = conn.execute("PRAGMA journal_mode = WAL;").fetchone()
            if mode_row is None or str(mode_row[0]).lower() != "wal":
                raise RuntimeError(
                    f"Failed to enable SQLite WAL journal mode (got: {mode_row[0] if mode_row else None})"
                )

            conn.executescript(schema_sql)
            # Re-apply foreign_keys after executescript implicit commit
            conn.execute("PRAGMA foreign_keys = ON;")

            try:
                conn.execute("SELECT * FROM notes_fts LIMIT 0").fetchall()
            except sqlite3.OperationalError as exc:
                raise RuntimeError(
                    "SQLite FTS5 extension is required but unavailable in this Python runtime"
                ) from exc

            conn.commit()
