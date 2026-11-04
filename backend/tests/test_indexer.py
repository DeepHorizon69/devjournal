from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.db.connection import get_db_connection, get_db_transaction, init_db
from app.main import app
from app.models.note import NoteFrontmatter
from app.repositories.notes_repo import NotesRepository
from app.services.frontmatter_svc import parse_markdown_note
from app.services.indexer_svc import (
    HashConflictError,
    IndexerService,
    compute_collision_id,
)
from app.services.vault_storage import VaultStorageService


def _setup_test_env(tmp_path: Path) -> tuple[Path, Path, VaultStorageService, NotesRepository, IndexerService]:
    data_dir = tmp_path / "devjournal-data"
    vault_dir = data_dir / "vault"
    db_path = data_dir / "devjournal.db"

    vault_svc = VaultStorageService(vault_dir)
    vault_svc.ensure_vault_structure()
    init_db(db_path)

    repo = NotesRepository()
    indexer = IndexerService(vault_storage=vault_svc, repo=repo, db_path=db_path)
    return vault_dir, db_path, vault_svc, repo, indexer


def test_reconcile_vault_indexes_notes_and_inbox_semantics_and_fts(tmp_path: Path) -> None:
    _vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)

    vault_svc.write_markdown_atomic(
        "00-Inbox/quick-idea.md",
        "# Quick Packet Capture Idea\n\nUse tcpdump with ring buffer flags.\n",
    )
    vault_svc.write_markdown_atomic(
        "10-Notes/bgp-routing.md",
        "---\nid: \"note-bgp\"\ntitle: \"BGP Multipath Routing\"\ntype: \"note\"\ndomains:\n  - Networking\ntags:\n  - bgp\n  - routing\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\n## ECMP\n\nBGP multipath load balances across equal-cost AS paths.\n",
    )
    vault_svc.write_markdown_atomic(
        "30-Experiments/esp32-deep-sleep.md",
        "# ESP32 Deep Sleep Current\n\nMeasured 12 microamps on custom PCB.\n",
    )

    res = indexer.reconcile_vault()
    assert res.status == "ok"
    assert res.indexed == 3
    assert res.updated == 0
    assert res.unchanged == 0
    assert res.removed == 0

    inbox_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "devjournal:00-Inbox/quick-idea.md"))
    with get_db_connection(db_path) as conn:
        inbox_note = repo.get_note_by_id(conn, inbox_id)
        assert inbox_note is not None
        assert inbox_note.folder == "00-Inbox"
        assert inbox_note.note_type == "note"

        bgp_note = repo.get_note_by_id(conn, "note-bgp")
        assert bgp_note is not None
        assert bgp_note.domains == ["Networking"]
        assert bgp_note.tags == ["bgp", "routing"]

        fts_rows = conn.execute(
            "SELECT note_id FROM notes_fts WHERE notes_fts MATCH 'multipath'"
        ).fetchall()
        assert [r["note_id"] for r in fts_rows] == ["note-bgp"]


def test_hash_verified_reconciliation_detects_edit_with_unchanged_mtime(
    tmp_path: Path,
) -> None:
    vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)

    rel_path = "10-Notes/mtime-spoof.md"
    target_path, orig_mtime = vault_svc.write_markdown_atomic(
        rel_path,
        "---\nid: \"mtime-note\"\ntitle: \"Original Title\"\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\nInitial body text.\n",
    )

    res1 = indexer.reconcile_vault()
    assert res1.indexed == 1

    # Modify file content on disk and force st_mtime back to exact orig_mtime
    vault_svc.write_markdown_atomic(
        rel_path,
        "---\nid: \"mtime-note\"\ntitle: \"Modified Title\"\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\nCompletely changed body with unique_token_xyz.\n",
    )
    os.utime(target_path, (orig_mtime, orig_mtime))
    assert abs(target_path.stat().st_mtime - orig_mtime) < 1e-6

    res2 = indexer.reconcile_vault()
    assert res2.updated == 1
    assert res2.unchanged == 0

    with get_db_connection(db_path) as conn:
        rec = repo.get_note_by_id(conn, "mtime-note")
        assert rec is not None
        assert rec.title == "Modified Title"

        fts_hits = conn.execute(
            "SELECT note_id FROM notes_fts WHERE notes_fts MATCH 'unique_token_xyz'"
        ).fetchall()
        assert len(fts_hits) == 1
        assert fts_hits[0]["note_id"] == "mtime-note"


def test_file_rename_preserves_note_and_fts_entry(tmp_path: Path) -> None:
    vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)

    id_a = "aaaa1111-2222-3333-4444-555555555555"
    vault_svc.write_markdown_atomic(
        "10-Notes/original-name.md",
        f"---\nid: \"{id_a}\"\ntitle: \"Rename Test Note\"\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\nBody containing special_rename_keyword for FTS.\n",
    )

    indexer.reconcile_vault()

    # Rename file on disk without changing frontmatter UUID
    os.replace(
        vault_dir / "10-Notes" / "original-name.md",
        vault_dir / "10-Notes" / "renamed-note.md",
    )

    res = indexer.reconcile_vault()
    assert res.updated == 1
    assert res.removed == 0

    with get_db_connection(db_path) as conn:
        total = conn.execute("SELECT count(*) FROM notes").fetchone()[0]
        assert total == 1

        rec = repo.get_note_by_id(conn, id_a)
        assert rec is not None
        assert rec.rel_path == "10-Notes/renamed-note.md"

        fts_hits = conn.execute(
            "SELECT note_id FROM notes_fts WHERE notes_fts MATCH 'special_rename_keyword'"
        ).fetchall()
        assert [r["note_id"] for r in fts_hits] == [id_a]


def test_duplicate_uuid_collision_and_canonical_promotion_on_save(
    tmp_path: Path,
) -> None:
    vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)

    md_a = "---\nid: \"dup-uuid\"\ntitle: \"First Note\"\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\nFirst body.\n"
    md_b = "---\nid: \"dup-uuid\"\ntitle: \"Second Note\"\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\nSecond body.\n"

    vault_svc.write_markdown_atomic("10-Notes/a.md", md_a)
    vault_svc.write_markdown_atomic("10-Notes/b.md", md_b)

    res1 = indexer.reconcile_vault()
    assert res1.indexed == 2
    assert res1.warnings == 1
    assert any("10-Notes/a.md" in w and "10-Notes/b.md" in w for w in res1.warning_details)

    # Neither file on disk was modified during read-only reconciliation
    assert vault_svc.read_markdown("10-Notes/a.md")[0] == md_a
    assert vault_svc.read_markdown("10-Notes/b.md")[0] == md_b

    expected_collision_id = compute_collision_id("dup-uuid", "10-Notes/b.md")
    with get_db_connection(db_path) as conn:
        rec_a = repo.get_note_by_id(conn, "dup-uuid")
        rec_b = repo.get_note_by_id(conn, expected_collision_id)
        assert rec_a is not None and rec_a.rel_path == "10-Notes/a.md"
        assert rec_b is not None and rec_b.rel_path == "10-Notes/b.md"

    # Subsequent reconcile with no disk changes keeps collision_id as unchanged
    res2 = indexer.reconcile_vault()
    assert res2.unchanged == 2
    assert res2.indexed == 0
    assert res2.updated == 0
    assert res2.warnings == 1

    # Explicit save of 10-Notes/b.md promotes collision_id into canonical frontmatter on disk
    fm_b = NoteFrontmatter(
        id="dup-uuid",
        title="Second Note Saved",
        type="note",
        created_at="2026-11-04T09:00:00Z",
        updated_at="2026-11-04T10:00:00Z",
    )
    parsed_b, index_ok = indexer.write_and_index_note(
        fm_b, "Updated second body.\n", "10-Notes/b.md"
    )
    assert index_ok is True
    assert parsed_b.metadata.id == expected_collision_id

    disk_b_text, disk_b_mtime = vault_svc.read_markdown("10-Notes/b.md")
    reparsed_b = parse_markdown_note(disk_b_text, "10-Notes/b.md", disk_b_mtime)
    assert reparsed_b.raw_frontmatter_id == expected_collision_id
    assert reparsed_b.metadata.id == expected_collision_id


def test_invalid_utf8_exclusion_and_scan_resilience(tmp_path: Path) -> None:
    vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)

    vault_svc.write_markdown_atomic("10-Notes/valid.md", "# Valid Note\n\nGood UTF-8.\n")
    corrupt_path = vault_dir / "10-Notes" / "corrupt.md"
    corrupt_bytes = b"---\ntitle: Bad\n---\n\xff\xfe"
    corrupt_path.write_bytes(corrupt_bytes)

    res_reconcile = indexer.reconcile_vault()
    assert res_reconcile.indexed == 1
    assert res_reconcile.warnings >= 1
    assert any("not valid UTF-8" in w for w in res_reconcile.warning_details)
    assert corrupt_path.read_bytes() == corrupt_bytes

    res_full = indexer.full_reindex()
    assert res_full.indexed == 1
    assert res_full.warnings >= 1
    assert any("not valid UTF-8" in w for w in res_full.warning_details)
    assert corrupt_path.read_bytes() == corrupt_bytes

    with get_db_connection(db_path) as conn:
        assert repo.count_active_notes(conn) == 1
        rows = conn.execute("SELECT rel_path FROM notes").fetchall()
        assert [r["rel_path"] for r in rows] == ["10-Notes/valid.md"]


@pytest.mark.asyncio
async def test_full_reindex_preserves_last_opened_at_and_handles_faulty_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path / "devjournal-data")

    vault_svc.write_markdown_atomic(
        "10-Notes/opened-note.md",
        "---\nid: \"opened-1\"\ntitle: \"Opened Note\"\ncreated_at: \"2026-11-04T09:00:00Z\"\nupdated_at: \"2026-11-04T09:00:00Z\"\n---\nBody text.\n",
    )
    # Add 4 faulty YAML shapes (malformed, scalar, list, empty)
    vault_svc.write_markdown_atomic(
        "10-Notes/malformed.md", "---\ntitle: [unclosed\n---\nMalformed body.\n"
    )
    vault_svc.write_markdown_atomic(
        "10-Notes/scalar.md", "---\njust a scalar\n---\nScalar body.\n"
    )
    vault_svc.write_markdown_atomic(
        "10-Notes/list.md", "---\n- item1\n- item2\n---\nList body.\n"
    )
    vault_svc.write_markdown_atomic(
        "10-Notes/empty-fm.md", "---\n---\nEmpty frontmatter body.\n"
    )

    indexer.reconcile_vault()

    with get_db_transaction(db_path) as conn:
        conn.execute(
            "UPDATE notes SET last_opened_at = ? WHERE id = ?",
            ("2026-11-04T15:00:00Z", "opened-1"),
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/system/reindex")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["indexed"] == 5
        assert data["warnings"] == 4

    with get_db_connection(db_path) as conn:
        opened_rec = repo.get_note_by_id(conn, "opened-1")
        assert opened_rec is not None
        assert opened_rec.last_opened_at == "2026-11-04T15:00:00Z"


def test_write_and_index_note_concurrency_and_sqlite_failure_healing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _vault_dir, db_path, vault_svc, repo, indexer = _setup_test_env(tmp_path)

    fm = NoteFrontmatter(
        id="write-test-1",
        title="Write Then Index Note",
        type="note",
        status="active",
        created_at="2026-11-04T09:00:00Z",
        updated_at="2026-11-04T09:00:00Z",
    )
    parsed_1, ok_1 = indexer.write_and_index_note(
        fm, "Initial body.\n", "10-Notes/write-test.md"
    )
    assert ok_1 is True

    # Mismatched expected_hash raises HashConflictError
    with pytest.raises(HashConflictError) as exc_info:
        indexer.write_and_index_note(
            fm,
            "Conflicting update.\n",
            "10-Notes/write-test.md",
            expected_hash="0" * 64,
        )
    assert exc_info.value.current_hash == parsed_1.content_hash

    # Matching expected_hash succeeds
    fm_v2 = fm.model_copy(update={"title": "Write Then Index V2"})
    parsed_2, ok_2 = indexer.write_and_index_note(
        fm_v2,
        "Second body.\n",
        "10-Notes/write-test.md",
        expected_hash=parsed_1.content_hash,
    )
    assert ok_2 is True
    assert parsed_2.metadata.title == "Write Then Index V2"

    # Simulate SQLite error during index phase after canonical Markdown disk write
    def fail_upsert(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise sqlite3.OperationalError("simulated sqlite lock error")

    monkeypatch.setattr(repo, "upsert_parsed_note", fail_upsert)

    fm_v3 = fm.model_copy(update={"title": "Write Then Index V3"})
    parsed_3, ok_3 = indexer.write_and_index_note(
        fm_v3,
        "Third body saved on disk despite DB error.\n",
        "10-Notes/write-test.md",
        expected_hash=parsed_2.content_hash,
    )
    assert ok_3 is False
    disk_text, _ = vault_svc.read_markdown("10-Notes/write-test.md")
    assert "Third body saved on disk despite DB error." in disk_text

    # Restore repo.upsert_parsed_note and verify reconcile_vault() heals the SQLite index
    monkeypatch.undo()
    heal_res = indexer.reconcile_vault()
    assert heal_res.updated == 1

    with get_db_connection(db_path) as conn:
        healed = repo.get_note_by_id(conn, "write-test-1")
        assert healed is not None
        assert healed.title == "Write Then Index V3"
        assert healed.content_hash == parsed_3.content_hash
