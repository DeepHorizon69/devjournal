from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import Settings
from app.services.vault_storage import (
    CANONICAL_VAULT_FOLDERS,
    InvalidEncodingError,
    InvalidTrashOperationError,
    NoteFileExistsError,
    NoteFileNotFoundError,
    PathTraversalError,
    VaultStorageService,
    slugify_title,
)


def test_single_ownership_of_vault_directory_initialization(tmp_path: Path) -> None:
    data_dir = tmp_path / "devjournal-data"
    cfg = Settings(data_dir=data_dir)
    cfg.ensure_directories()

    # Settings.ensure_directories() creates only data_dir, vault_dir, backups_dir
    assert cfg.data_dir.is_dir()
    assert cfg.vault_dir.is_dir()
    assert cfg.backups_dir.is_dir()
    assert list(cfg.vault_dir.iterdir()) == []

    # VaultStorageService.ensure_vault_structure() is the sole initializer of the 8 canonical folders
    svc = VaultStorageService(cfg.vault_dir)
    svc.ensure_vault_structure()

    created_folders = sorted(p.name for p in cfg.vault_dir.iterdir() if p.is_dir())
    assert created_folders == sorted(CANONICAL_VAULT_FOLDERS)


def test_resolve_safe_path_accepts_canonical_and_rejects_traversal(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    p1 = svc.resolve_safe_path("10-Notes/my-note.md")
    assert p1 == (vault_dir / "10-Notes" / "my-note.md").resolve()

    p2 = svc.resolve_safe_path("00-Inbox/quick.md")
    assert p2 == (vault_dir / "00-Inbox" / "quick.md").resolve()

    invalid_paths = [
        "",
        "   ",
        "../outside.md",
        "10-Notes/../../etc/passwd",
        "10-Notes/../outside.md",
        "/etc/passwd",
        r"\Windows\win.ini",
        r"C:\Windows\win.ini",
        "10-Notes/bad\x00.md",
        "InvalidFolder/note.md",
        "root-note.md",
        "10-Notes/not-markdown.txt",
        "10-Notes/./note.md",
    ]
    for bad in invalid_paths:
        with pytest.raises(PathTraversalError):
            svc.resolve_safe_path(bad)

    # Test symlink escape if OS supports symlink creation in temp dir
    outside_file = tmp_path / "outside-secret.md"
    outside_file.write_text("secret", encoding="utf-8")
    symlink_path = vault_dir / "10-Notes" / "evil-link.md"
    try:
        os.symlink(outside_file, symlink_path)
    except (OSError, NotImplementedError):
        pass
    else:
        with pytest.raises(PathTraversalError):
            svc.resolve_safe_path("10-Notes/evil-link.md")


def test_iter_markdown_files_restricted_to_canonical_folders(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    # Valid canonical files
    svc.write_markdown_atomic("00-Inbox/capture.md", "# Capture\n")
    svc.write_markdown_atomic("10-Notes/alpha.md", "# Alpha\n")
    svc.write_markdown_atomic("30-Experiments/sub/exp.md", "# Exp\n")

    # Ignored files: root-level .md, non-canonical folder, dotfile, .tmp-* file
    (vault_dir / "stray-root.md").write_text("# Stray\n", encoding="utf-8")
    non_canonical = vault_dir / "88-Custom"
    non_canonical.mkdir()
    (non_canonical / "ignored.md").write_text("# Ignored\n", encoding="utf-8")
    (vault_dir / "10-Notes" / ".hidden.md").write_text("# Hidden\n", encoding="utf-8")
    (vault_dir / "10-Notes" / ".tmp-12345.md").write_text("# Temp\n", encoding="utf-8")

    items = svc.iter_markdown_files()
    rel_paths = [rel for rel, _, _ in items]
    assert rel_paths == [
        "00-Inbox/capture.md",
        "10-Notes/alpha.md",
        "30-Experiments/sub/exp.md",
    ]


def test_write_markdown_atomic_normalizes_crlf_and_cleans_temp_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_dir = tmp_path / "vault"
    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    target, mtime = svc.write_markdown_atomic(
        "10-Notes/line-endings.md", "Line 1\r\nLine 2\rLine 3\r\n"
    )
    assert target.read_bytes() == b"Line 1\nLine 2\nLine 3\n"
    assert mtime > 0

    def fail_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("Simulated os.replace failure")

    monkeypatch.setattr("app.services.vault_storage.os.replace", fail_replace)

    with pytest.raises(OSError, match="Simulated os.replace failure"):
        svc.write_markdown_atomic("10-Notes/line-endings.md", "Updated content\n")

    # Original file must be intact and no .tmp-*.md files left behind
    assert target.read_bytes() == b"Line 1\nLine 2\nLine 3\n"
    leftover_temps = list((vault_dir / "10-Notes").glob(".tmp-*.md"))
    assert leftover_temps == []


def test_strict_utf8_reading_raises_invalid_encoding_and_preserves_bytes(
    tmp_path: Path,
) -> None:
    vault_dir = tmp_path / "vault"
    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    bad_path = vault_dir / "10-Notes" / "bad-utf8.md"
    raw_invalid = b"\xff\xfe\x00\x80invalid"
    bad_path.write_bytes(raw_invalid)

    with pytest.raises(InvalidEncodingError, match="not valid UTF-8"):
        svc.read_markdown("10-Notes/bad-utf8.md")

    assert bad_path.read_bytes() == raw_invalid


def test_move_note_overwrite_guard_and_atomic_rename_first(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    svc.write_markdown_atomic("10-Notes/source.md", "Source content\n")
    svc.write_markdown_atomic("20-Projects/existing.md", "Existing destination\n")

    with pytest.raises(NoteFileExistsError):
        svc.move_note(
            "10-Notes/source.md",
            "20-Projects/existing.md",
            updated_content="Should not overwrite\n",
            allow_overwrite=False,
        )

    assert svc.read_markdown("10-Notes/source.md")[0] == "Source content\n"
    assert svc.read_markdown("20-Projects/existing.md")[0] == "Existing destination\n"


def test_crash_safe_trash_and_restore_fault_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.db.connection import get_db_connection, init_db
    from app.repositories.notes_repo import NotesRepository
    from app.services.indexer_svc import IndexerService

    vault_dir = tmp_path / "vault"
    db_path = tmp_path / "devjournal.db"
    init_db(db_path)

    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    svc.write_markdown_atomic(
        "10-Notes/crash-trash.md",
        "---\nid: \"11111111-2222-3333-4444-555555555555\"\ntitle: \"Crash Trash\"\ntrashed: false\n---\nOriginal active note\n",
    )
    svc.write_markdown_atomic(
        "99-Trash/crash-restore.md",
        "---\nid: \"66666666-7777-8888-9999-000000000000\"\ntitle: \"Crash Restore\"\ntrashed: true\noriginal_rel_path: \"10-Notes/crash-restore.md\"\n---\nOriginal trashed note\n",
    )

    def simulated_crash(rel_path: str, content: str) -> tuple[Path, float]:
        raise OSError("simulated crash after os.replace")

    monkeypatch.setattr(svc, "write_markdown_atomic", simulated_crash)

    # 1. Fault during move_to_trash after os.replace
    with pytest.raises(OSError, match="simulated crash after os.replace"):
        svc.move_to_trash(
            "10-Notes/crash-trash.md",
            note_id="11111111-2222-3333-4444-555555555555",
            trashed_content="Updated trash metadata\n",
        )

    assert not (vault_dir / "10-Notes" / "crash-trash.md").exists()
    assert (vault_dir / "99-Trash" / "crash-trash.md").is_file()

    # 2. Fault during restore_from_trash after os.replace
    with pytest.raises(OSError, match="simulated crash after os.replace"):
        svc.restore_from_trash(
            "99-Trash/crash-restore.md",
            original_rel_path="10-Notes/crash-restore.md",
            fallback_folder="10-Notes",
            title="Crash Restore",
            note_id="66666666-7777-8888-9999-000000000000",
            restored_content="Updated active metadata\n",
        )

    assert not (vault_dir / "99-Trash" / "crash-restore.md").exists()
    assert (vault_dir / "10-Notes" / "crash-restore.md").is_file()

    # 3. Verify startup reconciliation uses folder state as authoritative
    repo = NotesRepository()
    indexer = IndexerService(vault_storage=svc, repo=repo, db_path=db_path)
    res = indexer.reconcile_vault()
    assert res.indexed == 2

    with get_db_connection(db_path) as conn:
        trashed_rec = repo.get_note_by_id(conn, "11111111-2222-3333-4444-555555555555")
        restored_rec = repo.get_note_by_id(conn, "66666666-7777-8888-9999-000000000000")

    assert trashed_rec is not None
    assert trashed_rec.rel_path == "99-Trash/crash-trash.md"
    assert trashed_rec.is_trashed is True

    assert restored_rec is not None
    assert restored_rec.rel_path == "10-Notes/crash-restore.md"
    assert restored_rec.is_trashed is False
    assert restored_rec.original_rel_path is None

def test_collision_resolution_and_trash_delete_restrictions(tmp_path: Path) -> None:
    vault_dir = tmp_path / "vault"
    svc = VaultStorageService(vault_dir)
    svc.ensure_vault_structure()

    note_id_1 = "abcdef12-0000-0000-0000-000000000001"
    note_id_2 = "abcdef12-0000-0000-0000-000000000002"

    p1 = svc.generate_unique_rel_path("10-Notes", "My Topic!", note_id_1)
    assert p1 == "10-Notes/my-topic.md"
    svc.write_markdown_atomic(p1, "Note 1\n")

    # Same note keeping its own path
    assert (
        svc.generate_unique_rel_path(
            "10-Notes", "My Topic!", note_id_1, existing_rel_path=p1
        )
        == "10-Notes/my-topic.md"
    )

    # Second note with colliding title
    p2 = svc.generate_unique_rel_path("10-Notes", "My Topic!", note_id_2)
    assert p2 == "10-Notes/my-topic-abcdef12.md"
    svc.write_markdown_atomic(p2, "Note 2\n")

    # Third note with colliding title and same short prefix
    p3 = svc.generate_unique_rel_path("10-Notes", "My Topic!", note_id_2)
    assert p3 == "10-Notes/my-topic-abcdef12-2.md"

    # Daily note keeps YYYY-MM-DD filename
    daily_p = svc.generate_unique_rel_path("90-Daily", "2026-11-04", note_id_1)
    assert daily_p == "90-Daily/2026-11-04.md"

    # Permanent delete is forbidden outside 99-Trash unless allow_non_trash=True
    with pytest.raises(InvalidTrashOperationError):
        svc.delete_permanently(p1)
    assert (vault_dir / p1).is_file()

    # Move p1 to trash, then move p2 to trash with same stem if colliding
    trash_p1, _, _ = svc.move_to_trash(p1, note_id_1, "Trashed 1\n")
    assert trash_p1 == "99-Trash/my-topic.md"

    # Restore when original path is occupied falls back to unique path
    svc.write_markdown_atomic("10-Notes/my-topic.md", "Occupying original path\n")
    restored_rel, _, _ = svc.restore_from_trash(
        trash_p1,
        original_rel_path="10-Notes/my-topic.md",
        fallback_folder="10-Notes",
        title="My Topic!",
        note_id=note_id_1,
        restored_content="Restored 1\n",
    )
    assert restored_rel == "10-Notes/my-topic-abcdef12-2.md"

    # Trash again and permanently delete from 99-Trash
    trash_again, _, _ = svc.move_to_trash(restored_rel, note_id_1, "Trashed again\n")
    svc.delete_permanently(trash_again)
    assert not (vault_dir / trash_again).exists()

    # Delete non-existent raises NoteFileNotFoundError
    with pytest.raises(NoteFileNotFoundError):
        svc.delete_permanently("99-Trash/does-not-exist.md")

    # Explicit internal allow_non_trash=True works
    svc.delete_permanently(p2, allow_non_trash=True)
    assert not (vault_dir / p2).exists()


def test_slugify_title_edge_cases() -> None:
    assert slugify_title("WireGuard MTU & MSS Clamping!") == "wireguard-mtu-mss-clamping"
    assert slugify_title("   ---   ", fallback_id="12345678-90ab") == "untitled-12345678"
    assert slugify_title("   ---   ") == "untitled"
    assert len(slugify_title("a" * 120)) == 80
