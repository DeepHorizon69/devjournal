from __future__ import annotations

import io
import json
import threading
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import (
    RestoreInProgressError,
    get_db_connection,
    get_db_transaction,
    init_db,
    maintenance_gate,
)
from app.main import app
from app.services.backup_svc import BackupService
from app.services.vault_storage import (
    CANONICAL_VAULT_FOLDERS,
    PayloadTooLargeError,
    VaultStorageService,
)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data_dir = tmp_path / "devjournal-data"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    maintenance_gate.reset_for_testing()
    settings.ensure_directories()
    VaultStorageService(settings.vault_dir, db_path=settings.db_path).ensure_vault_structure()
    init_db(settings.db_path)
    with TestClient(app) as client:
        yield client
    maintenance_gate.reset_for_testing()


def test_markdown_import_and_export_roundtrip(api_client: TestClient) -> None:
    raw_md = "# Imported Engineering Note\n\nContent with **bold** and `code`.\n"
    import_res = api_client.post(
        "/api/v1/system/import-md",
        files={"file": ("networking-guide.md", raw_md.encode("utf-8"), "text/markdown")},
        data={"folder": "10-Notes"},
    )
    assert import_res.status_code == 201
    imported = import_res.json()
    assert imported["title"] == "Imported Engineering Note"
    assert imported["folder"] == "10-Notes"
    assert "Content with **bold**" in imported["body"]

    # Reject non-.md upload
    bad_ext = api_client.post(
        "/api/v1/system/import-md",
        files={"file": ("bad.txt", b"hello", "text/plain")},
    )
    assert bad_ext.status_code == 400
    assert bad_ext.json()["error"]["code"] == "INVALID_FILE_TYPE"

    # Export note
    export_res = api_client.get(f"/api/v1/notes/{imported['id']}/export")
    assert export_res.status_code == 200
    assert "attachment; filename=" in export_res.headers["content-disposition"]
    assert imported["id"] in export_res.text


def test_settings_canonical_key_and_legacy_migration(api_client: TestClient) -> None:
    """P1-6: Verify legacy 'app_preferences' and 'app_settings' migrate cleanly to 'editor_preferences'."""
    # Seed legacy 'app_preferences' key directly in SQLite
    with get_db_transaction(settings.db_path) as conn:
        conn.execute("DELETE FROM settings;")
        conn.execute(
            "INSERT INTO settings (key, value_json, updated_at) VALUES (?, ?, ?)",
            (
                "app_preferences",
                json.dumps(
                    {
                        "default_editor_mode": "raw",
                        "editor_font_size": 16,
                        "editor_word_wrap": False,
                        "autosave_delay_ms": 1500,
                    }
                ),
                "2026-11-04T08:00:00Z",
            ),
        )

    # GET /api/v1/settings reads the legacy row
    get_res = api_client.get("/api/v1/settings")
    assert get_res.status_code == 200
    prefs = get_res.json()
    assert prefs["default_editor_mode"] == "raw"
    assert prefs["editor_font_size"] == 16
    assert prefs["editor_word_wrap"] is False
    assert prefs["autosave_delay_ms"] == 1500

    # PUT /api/v1/settings persists under 'editor_preferences' and deletes legacy keys
    put_res = api_client.put(
        "/api/v1/settings",
        json={
            "default_editor_mode": "preview",
            "editor_font_size": 18,
            "editor_word_wrap": True,
            "autosave_delay_ms": 2000,
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["default_editor_mode"] == "preview"

    with get_db_connection(settings.db_path) as conn:
        keys = [
            r["key"]
            for r in conn.execute("SELECT key FROM settings").fetchall()
        ]
    assert keys == ["editor_preferences"]


def test_empty_vault_backup_and_restore_round_trip(api_client: TestClient) -> None:
    """P1-1 & Gate 5: Backup an empty vault (0 notes), populate vault, then restore empty backup."""
    # 1. Backup empty vault
    empty_bkp = api_client.post("/api/v1/system/backup")
    assert empty_bkp.status_code == 200
    bkp_filename = empty_bkp.json()["filename"]
    bkp_path = settings.backups_dir / bkp_filename
    assert bkp_path.is_file()

    # Verify manifest inside empty backup has note_file_count == 0
    with zipfile.ZipFile(bkp_path, "r") as zf:
        manifest = json.loads(zf.read("backup-manifest.json").decode("utf-8"))
        assert manifest["format_version"] == 1
        assert manifest["note_file_count"] == 0
        assert manifest["files"] == {}

    # 2. Populate vault with active and trashed notes
    n1 = api_client.post(
        "/api/v1/notes", json={"title": "Post Backup Note 1", "body": "Body 1\n"}
    ).json()
    n2 = api_client.post(
        "/api/v1/notes", json={"title": "Post Backup Note 2", "body": "Body 2\n"}
    ).json()
    api_client.delete(f"/api/v1/notes/{n2['id']}")
    assert api_client.get("/api/v1/notes").json()["total"] == 1
    assert api_client.get("/api/v1/notes", params={"trashed": True}).json()["total"] == 1

    # 3. Restore the empty-vault backup
    with open(bkp_path, "rb") as f:
        restore_res = api_client.post(
            "/api/v1/system/restore",
            files={"file": (bkp_filename, f, "application/zip")},
        )
    assert restore_res.status_code == 200
    assert restore_res.json()["indexed"] == 0

    # 4. Verify all 8 canonical vault folders exist and 0 notes remain
    for folder in CANONICAL_VAULT_FOLDERS:
        assert (settings.vault_dir / folder).is_dir()
    assert api_client.get("/api/v1/notes").json()["total"] == 0
    assert api_client.get("/api/v1/notes", params={"trashed": True}).json()["total"] == 0
    assert api_client.get(f"/api/v1/notes/{n1['id']}").status_code == 404


def test_full_snapshot_backup_restore_equivalence_and_safety_backup_download(
    api_client: TestClient,
) -> None:
    """Gate 5 & P1-5: Full snapshot restore equivalence and pre-restore safety backup download."""
    n1 = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Snapshot Note Alpha",
            "template_id": "experiment",
            "body": "Original Alpha Body\n",
        },
    ).json()
    # Open n1 to record last_opened_at
    opened_n1 = api_client.get(f"/api/v1/notes/{n1['id']}").json()
    orig_last_opened = opened_n1["last_opened_at"]
    assert orig_last_opened is not None

    api_client.put(
        "/api/v1/settings",
        json={
            "default_editor_mode": "raw",
            "editor_font_size": 17,
            "editor_word_wrap": False,
            "autosave_delay_ms": 1800,
        },
    )

    # Create snapshot backup
    bkp_res = api_client.post("/api/v1/system/backup")
    assert bkp_res.status_code == 200
    bkp_name = bkp_res.json()["filename"]

    # Download standard backup via GET /api/v1/system/backups/{filename}
    dl_std = api_client.get(f"/api/v1/system/backups/{bkp_name}")
    assert dl_std.status_code == 200
    bkp_bytes = dl_std.content

    # Modify n1, add n2, and change settings after backup
    api_client.put(
        f"/api/v1/notes/{n1['id']}",
        json={
            "title": "Modified Alpha",
            "note_type": "experiment",
            "status": "completed",
            "body": "Modified Alpha Body\n",
            "expected_hash": opened_n1["content_hash"],
        },
    )
    n2 = api_client.post(
        "/api/v1/notes",
        json={"title": "Ephemeral Note Beta", "body": "Should be removed on restore\n"},
    ).json()
    api_client.put(
        "/api/v1/settings",
        json={
            "default_editor_mode": "preview",
            "editor_font_size": 12,
            "editor_word_wrap": True,
            "autosave_delay_ms": 500,
        },
    )

    # Restore from snapshot backup
    restore_res = api_client.post(
        "/api/v1/system/restore",
        files={"file": (bkp_name, io.BytesIO(bkp_bytes), "application/zip")},
    )
    assert restore_res.status_code == 200
    restore_data = restore_res.json()
    assert restore_data["indexed"] == 1
    safety_name = restore_data["safety_backup_filename"]
    assert "-pre-restore-" in safety_name

    # Verify pre-restore safety backup is accepted by download validator (P1-5)
    dl_safety = api_client.get(f"/api/v1/system/backups/{safety_name}")
    assert dl_safety.status_code == 200

    # Verify traversal / invalid backup filenames are rejected
    for bad_name in ("../devjournal.db", "evil.zip", "devjournal-backup-bad.zip"):
        r = api_client.get(f"/api/v1/system/backups/{bad_name}")
        assert r.status_code in (400, 404)

    # Verify n2 is gone, n1 is restored with original content and last_opened_at, and settings match snapshot
    assert api_client.get(f"/api/v1/notes/{n2['id']}").status_code == 404
    restored_n1 = api_client.get(
        f"/api/v1/notes/{n1['id']}", params={"record_open": False}
    ).json()
    assert restored_n1["title"] == "Snapshot Note Alpha"
    assert restored_n1["body"] == "Original Alpha Body\n"
    assert restored_n1["last_opened_at"] == orig_last_opened

    restored_settings = api_client.get("/api/v1/settings").json()
    assert restored_settings["default_editor_mode"] == "raw"
    assert restored_settings["editor_font_size"] == 17


def test_backup_size_and_entry_limit_enforcement_on_create_backup(
    api_client: TestClient,
) -> None:
    """P1-1: Verify create_backup enforces note count, entry count, uncompressed bytes, and compressed bytes."""
    api_client.post(
        "/api/v1/notes",
        json={"title": "Limit Check Note", "body": "Some body text for limits\n"},
    )
    before_files = set(settings.backups_dir.iterdir())

    # 1. Exceed max_backup_note_files (set to 0)
    svc_note_limit = BackupService(settings.data_dir, max_backup_note_files=0)
    with pytest.raises(PayloadTooLargeError, match="exceeding backup limit"):
        svc_note_limit.create_backup()
    assert set(settings.backups_dir.iterdir()) == before_files

    # 2. Exceed max_archive_entries (set to 5)
    svc_entry_limit = BackupService(settings.data_dir, max_archive_entries=5)
    with pytest.raises(PayloadTooLargeError, match="entry count"):
        svc_entry_limit.create_backup()
    assert set(settings.backups_dir.iterdir()) == before_files

    # 3. Exceed max_uncompressed_bytes (set to 100 bytes)
    svc_uncomp_limit = BackupService(settings.data_dir, max_uncompressed_bytes=100)
    with pytest.raises(PayloadTooLargeError, match="uncompressed size"):
        svc_uncomp_limit.create_backup()
    assert set(settings.backups_dir.iterdir()) == before_files

    # 4. Exceed max_compressed_upload_bytes (set to 10 bytes)
    svc_comp_limit = BackupService(settings.data_dir, max_compressed_upload_bytes=10)
    with pytest.raises(PayloadTooLargeError, match="Compressed backup archive"):
        svc_comp_limit.create_backup()
    assert set(settings.backups_dir.iterdir()) == before_files


def test_backup_manifest_validation_rejects_missing_malformed_and_tampered_archives(
    api_client: TestClient,
) -> None:
    """P0-3: Test missing, malformed, version-mismatched, unknown-member, and SHA-256-tampered manifests."""
    api_client.post(
        "/api/v1/notes",
        json={"title": "Integrity Note", "body": "Untampered content\n"},
    )
    bkp_name = api_client.post("/api/v1/system/backup").json()["filename"]
    valid_zip_bytes = (settings.backups_dir / bkp_name).read_bytes()

    def mutate_zip(
        mutator,
    ) -> bytes:
        in_buf = io.BytesIO(valid_zip_bytes)
        out_buf = io.BytesIO()
        with zipfile.ZipFile(in_buf, "r") as zin, zipfile.ZipFile(
            out_buf, "w", compression=zipfile.ZIP_DEFLATED
        ) as zout:
            items = {name: zin.read(name) for name in zin.namelist()}
            mutator(items)
            for k, v in items.items():
                zout.writestr(k, v)
        return out_buf.getvalue()

    # 1. Missing backup-manifest.json
    missing_manifest = mutate_zip(lambda items: items.pop("backup-manifest.json", None))
    r1 = api_client.post(
        "/api/v1/system/restore",
        files={"file": ("missing.zip", io.BytesIO(missing_manifest), "application/zip")},
    )
    assert r1.status_code == 400
    assert r1.json()["error"]["code"] == "INVALID_ARCHIVE"

    # 2. Malformed backup-manifest.json
    malformed_manifest = mutate_zip(
        lambda items: items.__setitem__("backup-manifest.json", b"{not valid json")
    )
    r2 = api_client.post(
        "/api/v1/system/restore",
        files={"file": ("malformed.zip", io.BytesIO(malformed_manifest), "application/zip")},
    )
    assert r2.status_code == 400
    assert r2.json()["error"]["code"] == "INVALID_ARCHIVE"

    # 3. Unsupported format_version
    def set_bad_version(items: dict[str, bytes]) -> None:
        m = json.loads(items["backup-manifest.json"].decode("utf-8"))
        m["format_version"] = 99
        items["backup-manifest.json"] = json.dumps(m).encode("utf-8")

    bad_version = mutate_zip(set_bad_version)
    r3 = api_client.post(
        "/api/v1/system/restore",
        files={"file": ("badver.zip", io.BytesIO(bad_version), "application/zip")},
    )
    assert r3.status_code == 400

    # 4. Tampered Markdown file content (SHA-256 mismatch against manifest)
    def tamper_md(items: dict[str, bytes]) -> None:
        for k in list(items.keys()):
            if k.endswith(".md"):
                items[k] = items[k] + b"\nTampered line!\n"

    tampered = mutate_zip(tamper_md)
    r4 = api_client.post(
        "/api/v1/system/restore",
        files={"file": ("tampered.zip", io.BytesIO(tampered), "application/zip")},
    )
    assert r4.status_code == 400
    assert r4.json()["error"]["code"] == "INVALID_ARCHIVE"

    # 5. Unknown root member
    unknown_root = mutate_zip(
        lambda items: items.__setitem__("unexpected-root.txt", b"stray")
    )
    r5 = api_client.post(
        "/api/v1/system/restore",
        files={"file": ("unknown.zip", io.BytesIO(unknown_root), "application/zip")},
    )
    assert r5.status_code == 400
    assert r5.json()["error"]["code"] == "INVALID_ARCHIVE"


def test_active_request_draining_and_503_maintenance_gate_during_restore(
    api_client: TestClient,
) -> None:
    """P0-1 & Gate 5: Verify Restore drains already-running requests before acquiring db_write_lock and blocks new requests with 503."""
    n1 = api_client.post(
        "/api/v1/notes",
        json={"title": "Pre-Restore Note", "body": "Consistent pre-restore state\n"},
    ).json()
    bkp_name = api_client.post("/api/v1/system/backup").json()["filename"]
    bkp_bytes = (settings.backups_dir / bkp_name).read_bytes()

    # Add a second note after the backup so we can distinguish pre-restore (2 notes) from post-restore (1 note)
    api_client.post(
        "/api/v1/notes",
        json={"title": "Second Note Before Restore", "body": "Present before restore\n"},
    )

    lease_acquired_event = threading.Event()
    release_lease_event = threading.Event()
    restore_Entered_stage_4a_event = threading.Event()
    req_a_observed_total: list[int] = []
    req_b_status: list[int] = []
    health_during_maintenance: list[str] = []

    def simulate_in_flight_request_a() -> None:
        with maintenance_gate.acquire_request_lease():
            lease_acquired_event.set()
            # Wait until restore has started waiting to drain active leases
            release_lease_event.wait(timeout=5.0)
            # ReqA reads data while holding its pre-maintenance lease (before Restore can touch live data)
            with get_db_connection(settings.db_path) as conn:
                row = conn.execute(
                    "SELECT count(*) AS cnt FROM notes WHERE is_trashed = 0"
                ).fetchone()
                req_a_observed_total.append(int(row["cnt"]))

    orig_stage_4a = BackupService._apply_stage_4a_vault_replacement

    def hooked_stage_4a(self_svc: BackupService, staged_vault_dir: Path) -> None:
        restore_Entered_stage_4a_event.set()
        # While inside Stage 4a, a new request ReqB must receive 503 and /system/health must report 'maintenance'
        r_b = api_client.get("/api/v1/notes")
        req_b_status.append(r_b.status_code)
        r_health = api_client.get("/api/v1/system/health")
        health_during_maintenance.append(r_health.json()["status"])
        orig_stage_4a(self_svc, staged_vault_dir)

    thread_a = threading.Thread(target=simulate_in_flight_request_a)
    thread_a.start()
    assert lease_acquired_event.wait(timeout=5.0)

    restore_result_holder: list[int] = []

    def run_restore() -> None:
        res = api_client.post(
            "/api/v1/system/restore",
            files={"file": (bkp_name, io.BytesIO(bkp_bytes), "application/zip")},
        )
        restore_result_holder.append(res.status_code)

    # Monkeypatch Stage 4a to observe state during maintenance
    BackupService._apply_stage_4a_vault_replacement = hooked_stage_4a  # type: ignore[method-assign]
    try:
        restore_thread = threading.Thread(target=run_restore)
        restore_thread.start()

        # Wait until Restore has closed admission (_restore_in_progress == True) and is waiting for ReqA to drain
        for _ in range(100):
            if maintenance_gate.is_restore_in_progress:
                break
            threading.Event().wait(0.01)

        assert maintenance_gate.is_restore_in_progress is True
        # Restore must NOT have entered Stage 4a yet because ReqA still holds its lease!
        assert not restore_Entered_stage_4a_event.is_set()

        # Now let ReqA finish and release its lease
        release_lease_event.set()
        thread_a.join(timeout=5.0)
        restore_thread.join(timeout=10.0)
    finally:
        BackupService._apply_stage_4a_vault_replacement = orig_stage_4a  # type: ignore[method-assign]

    # Verify:
    # 1. ReqA observed the consistent pre-restore count (2 notes) before Restore mutated anything
    assert req_a_observed_total == [2]
    # 2. ReqB arriving during maintenance received 503 RESTORE_IN_PROGRESS
    assert req_b_status == [503]
    # 3. GET /api/v1/system/health remained available and reported 'maintenance'
    assert health_during_maintenance == ["maintenance"]
    # 4. Restore completed with 200 OK and released maintenance afterwards
    assert restore_result_holder == [200]
    assert maintenance_gate.is_restore_in_progress is False
    assert api_client.get("/api/v1/notes").json()["total"] == 1
    assert api_client.get("/api/v1/notes").json()["notes"][0]["id"] == n1["id"]


@pytest.mark.parametrize(
    "stage_method_name",
    [
        "_apply_stage_4a_vault_replacement",
        "_apply_stage_4b_settings_replacement",
        "_apply_stage_4c_full_reindex",
        "_apply_stage_4d_restore_last_opened",
    ],
)
def test_restore_failure_injection_across_all_4_stages_rolls_back_cleanly(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    stage_method_name: str,
) -> None:
    """Gate 5 & P0-1: Inject failure at each restore stage (4a, 4b, 4c, 4d) and verify complete rollback."""
    # Create baseline snapshot with 1 note
    api_client.post(
        "/api/v1/notes",
        json={"title": "Snapshot Note", "body": "Snapshot body\n"},
    )
    bkp_name = api_client.post("/api/v1/system/backup").json()["filename"]
    bkp_bytes = (settings.backups_dir / bkp_name).read_bytes()

    # Mutate live state before restore: add Live Note 2 and update settings
    live_n2 = api_client.post(
        "/api/v1/notes",
        json={"title": "Live Note Before Failed Restore", "body": "Must survive rollback\n"},
    ).json()
    api_client.put(
        "/api/v1/settings",
        json={
            "default_editor_mode": "raw",
            "editor_font_size": 19,
            "editor_word_wrap": False,
            "autosave_delay_ms": 2500,
        },
    )

    def fail_stage(*args, **kwargs):
        raise RuntimeError(f"Injected failure in {stage_method_name}")

    monkeypatch.setattr(BackupService, stage_method_name, fail_stage)

    with pytest.raises(RuntimeError, match=f"Injected failure in {stage_method_name}"):
        api_client.post(
            "/api/v1/system/restore",
            files={"file": (bkp_name, io.BytesIO(bkp_bytes), "application/zip")},
        )

    # Verify rollback succeeded, .restore-journal.json was removed, and pre-restore live state is intact!
    assert not (settings.data_dir / ".restore-journal.json").exists()
    assert maintenance_gate.is_blocked is False
    notes_after = api_client.get("/api/v1/notes").json()
    assert notes_after["total"] == 2
    assert any(n["id"] == live_n2["id"] for n in notes_after["notes"])
    settings_after = api_client.get("/api/v1/settings").json()
    assert settings_after["editor_font_size"] == 19


def test_rollback_failure_retains_journal_and_startup_recovery_fails_closed(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P1-4: Verify failed rollback retains .restore-journal.json & enters 503 degraded state, and unrecoverable startup fails closed."""
    api_client.post(
        "/api/v1/notes",
        json={"title": "Baseline Note", "body": "Baseline\n"},
    )
    bkp_name = api_client.post("/api/v1/system/backup").json()["filename"]
    bkp_bytes = (settings.backups_dir / bkp_name).read_bytes()

    monkeypatch.setattr(
        BackupService,
        "_apply_stage_4b_settings_replacement",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("Stage 4b failed")),
    )
    monkeypatch.setattr(
        BackupService,
        "_rollback_from_directory",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("Disk I/O failure during rollback")),
    )

    with pytest.raises(OSError, match="Disk I/O failure during rollback"):
        api_client.post(
            "/api/v1/system/restore",
            files={"file": (bkp_name, io.BytesIO(bkp_bytes), "application/zip")},
        )

    # 1. .restore-journal.json and .restore-rollback-* MUST be preserved on disk!
    journal_file = settings.data_dir / ".restore-journal.json"
    assert journal_file.is_file()
    rollback_dirs = list(settings.data_dir.glob(".restore-rollback-*"))
    assert len(rollback_dirs) == 1

    # 2. Application remains in protected 503 degraded state
    assert api_client.get("/api/v1/notes").status_code == 503
    assert api_client.get("/api/v1/system/health").json()["status"] == "degraded"

    # 3. While _rollback_from_directory is still failing, startup recovery must fail closed (raise RuntimeError)
    with pytest.raises(
        RuntimeError, match="Application startup aborted due to unrecoverable interrupted restore"
    ):
        BackupService(settings.data_dir).recover_interrupted_restore_if_any()
    assert journal_file.is_file()

    # Cleanup for fixture teardown
    journal_file.unlink(missing_ok=True)
    maintenance_gate.reset_for_testing()
