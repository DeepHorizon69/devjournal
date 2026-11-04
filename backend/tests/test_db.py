from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.db import (
    create_connection,
    get_db_connection,
    get_db_transaction,
    init_db,
)


def test_init_db_creates_schema_wal_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "subdir" / "devjournal.db"
    assert not db_path.exists()

    init_db(db_path)
    assert db_path.is_file()

    # Check Idempotency
    init_db(db_path)

    with get_db_connection(db_path) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert str(journal_mode).lower() == "wal"

        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        expected_tables = {"notes", "note_domains", "note_tags", "settings", "notes_fts"}
        assert expected_tables.issubset(tables)

        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        expected_indexes = {
            "idx_notes_type_trashed",
            "idx_notes_folder_trashed",
            "idx_notes_updated",
            "idx_notes_last_opened",
            "idx_note_domains_domain",
            "idx_note_tags_tag",
        }
        assert expected_indexes.issubset(indexes)
def test_connection_pragmas_and_no_wal_reexecution_on_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "devjournal.db"
    init_db(db_path)

    executed_statements: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):  # type: ignore[no-untyped-def]
        c = real_connect(*args, **kwargs)
        c.set_trace_callback(executed_statements.append)
        return c

    monkeypatch.setattr("app.db.connection.sqlite3.connect", traced_connect)

    conn = create_connection(db_path)
    try:
        assert not any("journal_mode" in stmt.lower() for stmt in executed_statements)
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]

        assert fk == 1
        assert busy_timeout == 5000
        assert synchronous == 1  # 1 == NORMAL
    finally:
        conn.close()


def test_get_db_connection_closes_on_exit(tmp_path: Path) -> None:
    db_path = tmp_path / "devjournal.db"
    init_db(db_path)

    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT 1 AS val").fetchone()
        assert row["val"] == 1

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_fts5_match_and_foreign_key_cascade(tmp_path: Path) -> None:
    db_path = tmp_path / "devjournal.db"
    init_db(db_path)

    with get_db_transaction(db_path) as conn:
        conn.execute(
            """
            INSERT INTO notes (
                id, title, slug, rel_path, folder, note_type, status,
                excerpt, word_count, reading_time_mins, content_hash,
                file_mtime, is_pinned, is_trashed, original_rel_path,
                created_at, updated_at, last_opened_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "note-1",
                "WireGuard MTU Debugging",
                "wireguard-mtu-debugging",
                "40-Troubleshooting/wireguard-mtu-debugging.md",
                "40-Troubleshooting",
                "troubleshooting",
                "resolved",
                "Fixing packet fragmentation over PPPoE links.",
                42,
                1,
                "a" * 64,
                1730712600.0,
                1,
                0,
                None,
                "2026-11-04T09:30:00Z",
                "2026-11-04T09:30:00Z",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO note_domains (note_id, domain) VALUES (?, ?)",
            ("note-1", "Networking"),
        )
        conn.execute(
            "INSERT INTO note_tags (note_id, tag) VALUES (?, ?)",
            ("note-1", "wireguard"),
        )
        conn.execute(
            """
            INSERT INTO notes_fts (note_id, title, headings, body, tags_text, domains_text)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "note-1",
                "WireGuard MTU Debugging",
                "Symptom \n Root Cause",
                "Packet fragmentation happens when PPPoE overhead reduces path MTU.",
                "wireguard mtu",
                "Networking",
            ),
        )

    with get_db_connection(db_path) as conn:
        fts_hits = conn.execute(
            "SELECT note_id FROM notes_fts WHERE notes_fts MATCH 'fragment*'"
        ).fetchall()
        assert len(fts_hits) == 1
        assert fts_hits[0]["note_id"] == "note-1"

    # Delete parent note and verify ON DELETE CASCADE removes note_domains and note_tags
    with get_db_transaction(db_path) as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", ("note-1",))

    with get_db_connection(db_path) as conn:
        domain_count = conn.execute(
            "SELECT count(*) FROM note_domains WHERE note_id = ?", ("note-1",)
        ).fetchone()[0]
        tag_count = conn.execute(
            "SELECT count(*) FROM note_tags WHERE note_id = ?", ("note-1",)
        ).fetchone()[0]
        assert domain_count == 0
        assert tag_count == 0


def test_get_db_transaction_rolls_back_on_error(tmp_path: Path) -> None:
    db_path = tmp_path / "devjournal.db"
    init_db(db_path)

    with pytest.raises(RuntimeError, match="abort tx"):
        with get_db_transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?)",
                ("theme", '"dark"', "2026-11-04T09:30:00Z"),
            )
            raise RuntimeError("abort tx")

    with get_db_connection(db_path) as conn:
        count = conn.execute("SELECT count(*) FROM settings").fetchone()[0]
        assert count == 0
