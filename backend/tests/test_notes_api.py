from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import init_db, maintenance_gate
from app.main import app
from app.services.vault_storage import VaultStorageService


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


def test_templates_catalog_and_general_note_null_status(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/templates")
    assert resp.status_code == 200
    templates = {t["id"]: t for t in resp.json()["templates"]}
    assert set(templates.keys()) == {
        "general",
        "experiment",
        "troubleshooting",
        "project",
        "daily",
    }
    assert templates["general"]["note_type"] == "note"
    assert templates["general"]["folder"] == "10-Notes"
    assert templates["general"]["default_status"] is None

    assert templates["experiment"]["default_status"] == "active"
    assert templates["troubleshooting"]["default_status"] == "investigating"
    assert templates["project"]["default_status"] == "active"
    assert templates["daily"]["default_status"] == "active"

    # 1. Create a General Note via template_id="general" without status -> status is None (null)
    create_gen = api_client.post(
        "/api/v1/notes",
        json={"title": "General Architecture Note", "template_id": "general"},
    )
    assert create_gen.status_code == 201
    gen_data = create_gen.json()
    assert gen_data["note_type"] == "note"
    assert gen_data["folder"] == "10-Notes"
    assert gen_data["status"] is None
    assert "## Overview" in gen_data["body"]

    # Verify disk frontmatter has status: null
    md_path = settings.vault_dir / gen_data["rel_path"]
    assert md_path.is_file()
    raw_text = md_path.read_text(encoding="utf-8")
    assert "status: null" in raw_text

    # 2. Create a note without template_id and without status -> status is None
    create_plain = api_client.post(
        "/api/v1/notes",
        json={"title": "Plain Note Without Template", "body": "Hello world\n"},
    )
    assert create_plain.status_code == 201
    assert create_plain.json()["status"] is None

    # 3. Override general template with explicit status="draft"
    create_override = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Draft General Note",
            "template_id": "general",
            "status": "draft",
        },
    )
    assert create_override.status_code == 201
    assert create_override.json()["status"] == "draft"

    # 4. Override experiment template (default "active") with explicit status=null
    create_exp_null = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Statusless Experiment",
            "template_id": "experiment",
            "status": None,
        },
    )
    assert create_exp_null.status_code == 201
    assert create_exp_null.json()["note_type"] == "experiment"
    assert create_exp_null.json()["status"] is None


def test_crud_title_slug_stability_inbox_preservation_and_folder_relocation(
    api_client: TestClient,
) -> None:
    # 1. Create note in 00-Inbox
    res = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Initial Topic Title",
            "note_type": "note",
            "folder": "00-Inbox",
            "domains": ["Networking", "Linux"],
            "tags": ["WireGuard", "MTU_Test"],
            "body": "Initial body content\n",
        },
    )
    assert res.status_code == 201
    note = res.json()
    note_id = note["id"]
    assert note["slug"] == "initial-topic-title"
    assert note["rel_path"] == "00-Inbox/initial-topic-title.md"
    assert note["tags"] == ["wireguard", "mtu-test"]

    # 2. Update title and change note_type while in 00-Inbox -> stays in 00-Inbox and keeps slug/filename!
    put_res = api_client.put(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Renamed Topic Title",
            "note_type": "experiment",
            "status": "active",
            "domains": ["Networking"],
            "tags": ["wireguard"],
            "is_pinned": True,
            "body": "Updated body in Inbox\n",
            "expected_hash": note["content_hash"],
        },
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["title"] == "Renamed Topic Title"
    assert updated["slug"] == "initial-topic-title"
    assert updated["rel_path"] == "00-Inbox/initial-topic-title.md"
    assert updated["folder"] == "00-Inbox"
    assert updated["note_type"] == "experiment"

    # 3. Explicitly move out of 00-Inbox to 30-Experiments via PATCH
    patch_res = api_client.patch(
        f"/api/v1/notes/{note_id}",
        json={
            "folder": "30-Experiments",
            "expected_hash": updated["content_hash"],
        },
    )
    assert patch_res.status_code == 200
    moved = patch_res.json()
    assert moved["folder"] == "30-Experiments"
    assert moved["rel_path"] == "30-Experiments/initial-topic-title.md"
    assert not (settings.vault_dir / "00-Inbox" / "initial-topic-title.md").exists()
    assert (settings.vault_dir / "30-Experiments" / "initial-topic-title.md").is_file()

    # 4. Changing note_type from 'experiment' (in 30-Experiments) to 'troubleshooting' (without explicit folder)
    # automatically relocates to 40-Troubleshooting
    patch_type = api_client.patch(
        f"/api/v1/notes/{note_id}",
        json={
            "note_type": "troubleshooting",
            "status": "investigating",
            "expected_hash": moved["content_hash"],
        },
    )
    assert patch_type.status_code == 200
    relocated = patch_type.json()
    assert relocated["folder"] == "40-Troubleshooting"
    assert relocated["rel_path"] == "40-Troubleshooting/initial-topic-title.md"

    # 5. Soft delete to Trash, then verify PUT and PATCH are rejected on trashed notes
    del_res = api_client.delete(f"/api/v1/notes/{note_id}")
    assert del_res.status_code == 200

    trashed_get = api_client.get(f"/api/v1/notes/{note_id}")
    assert trashed_get.status_code == 200
    trashed_hash = trashed_get.json()["content_hash"]

    put_trashed = api_client.put(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Cannot Edit Trash",
            "note_type": "troubleshooting",
            "body": "Blocked",
            "expected_hash": trashed_hash,
        },
    )
    assert put_trashed.status_code == 400
    assert put_trashed.json()["error"]["code"] == "INVALID_TRASH_OPERATION"

    patch_trashed = api_client.patch(
        f"/api/v1/notes/{note_id}",
        json={
            "is_pinned": False,
            "expected_hash": trashed_hash,
        },
    )
    assert patch_trashed.status_code == 400
    assert patch_trashed.json()["error"]["code"] == "INVALID_TRASH_OPERATION"


def test_optimistic_concurrency_on_put_and_patch(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/notes",
        json={"title": "Concurrency Target", "body": "Version 1\n"},
    ).json()
    note_id = created["id"]
    v1_hash = created["content_hash"]

    # 1. Missing expected_hash when force=False -> 400 MISSING_EXPECTED_HASH
    missing_hash_res = api_client.put(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Concurrency Target",
            "note_type": "note",
            "body": "Missing hash attempt\n",
            "force": False,
        },
    )
    assert missing_hash_res.status_code == 400
    assert missing_hash_res.json()["error"]["code"] == "MISSING_EXPECTED_HASH"

    # 2. Matching expected_hash -> 200 OK
    v2_res = api_client.put(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Concurrency Target",
            "note_type": "note",
            "body": "Version 2\n",
            "expected_hash": v1_hash,
        },
    )
    assert v2_res.status_code == 200
    v2_hash = v2_res.json()["content_hash"]
    assert v2_hash != v1_hash

    # 3. Stale expected_hash on PUT -> 409 CONFLICT_HASH_MISMATCH with zero disk/DB mutation
    stale_put = api_client.put(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Stale Overwrite",
            "note_type": "note",
            "body": "Should fail\n",
            "expected_hash": v1_hash,
        },
    )
    assert stale_put.status_code == 409
    err = stale_put.json()["error"]
    assert err["code"] == "CONFLICT_HASH_MISMATCH"
    assert err["details"]["current_hash"] == v2_hash
    assert err["details"]["expected_hash"] == v1_hash

    # Verify disk & DB still have Version 2
    check = api_client.get(f"/api/v1/notes/{note_id}").json()
    assert check["body"] == "Version 2\n"
    assert check["title"] == "Concurrency Target"

    # 4. Stale expected_hash on PATCH -> 409 CONFLICT_HASH_MISMATCH
    stale_patch = api_client.patch(
        f"/api/v1/notes/{note_id}",
        json={"is_pinned": True, "expected_hash": v1_hash},
    )
    assert stale_patch.status_code == 409
    assert stale_patch.json()["error"]["code"] == "CONFLICT_HASH_MISMATCH"

    # 5. force=True on PUT overwrites despite stale expected_hash
    force_put = api_client.put(
        f"/api/v1/notes/{note_id}",
        json={
            "title": "Forced Version 3",
            "note_type": "note",
            "body": "Version 3 forced\n",
            "expected_hash": v1_hash,
            "force": True,
        },
    )
    assert force_put.status_code == 200
    assert force_put.json()["body"] == "Version 3 forced\n"


def test_runtime_move_journal_recovery_without_restart_or_manual_reindex(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0-2: Inject failure between os.replace and destination content write, then immediately GET note."""
    created = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Move Crash Target",
            "note_type": "note",
            "body": "Original content before move\n",
        },
    ).json()
    note_id = created["id"]
    orig_hash = created["content_hash"]

    orig_write_atomic = VaultStorageService.write_markdown_atomic
    fail_once = {"armed": True}

    def crash_once_after_rename(
        self_svc: VaultStorageService, rel_path: str, content: str
    ):
        if fail_once["armed"] and rel_path.startswith("30-Experiments/"):
            fail_once["armed"] = False
            raise OSError("Simulated crash after os.replace before destination write")
        return orig_write_atomic(self_svc, rel_path, content)

    monkeypatch.setattr(
        VaultStorageService, "write_markdown_atomic", crash_once_after_rename
    )

    # Trigger PUT that moves note from 10-Notes to 30-Experiments AND updates body
    with pytest.raises(
        OSError, match="Simulated crash after os.replace before destination write"
    ):
        api_client.put(
            f"/api/v1/notes/{note_id}",
            json={
                "title": "Move Crash Target Updated",
                "note_type": "experiment",
                "status": "active",
                "body": "Updated content that was staged in move journal\n",
                "expected_hash": orig_hash,
            },
        )

    # Confirm .move-journal-*.json and .move-staged-*.tmp exist on disk right after the crash
    journals = list(settings.vault_dir.glob(".move-journal-*.json"))
    staged_files = list(settings.vault_dir.glob(".move-staged-*.tmp"))
    assert len(journals) == 1
    assert len(staged_files) == 1

    # Do NOT restart the app and do NOT call /api/v1/system/reindex.
    # Immediately call GET /api/v1/notes/{note_id}.
    get_res = api_client.get(f"/api/v1/notes/{note_id}")
    assert get_res.status_code == 200
    recovered = get_res.json()

    # Verify runtime recovery promoted staged content, updated SQLite, and cleaned up journal
    assert recovered["folder"] == "30-Experiments"
    assert recovered["rel_path"] == "30-Experiments/move-crash-target.md"
    assert recovered["note_type"] == "experiment"
    assert recovered["title"] == "Move Crash Target Updated"
    assert recovered["body"] == "Updated content that was staged in move journal\n"
    assert list(settings.vault_dir.glob(".move-journal-*.json")) == []
    assert list(settings.vault_dir.glob(".move-staged-*.tmp")) == []


def test_move_journal_collision_guard_and_path_traversal_protection(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0-2: Verify move recovery never overwrites an unrelated destination file and rejects traversal."""
    created = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Collision Move Note",
            "note_type": "note",
            "body": "Original note body\n",
        },
    ).json()
    note_id = created["id"]

    orig_write_atomic = VaultStorageService.write_markdown_atomic
    fail_once = {"armed": True}

    def crash_once(self_svc: VaultStorageService, rel_path: str, content: str):
        if fail_once["armed"] and rel_path.startswith("20-Projects/"):
            fail_once["armed"] = False
            raise OSError("Crash during move to 20-Projects")
        return orig_write_atomic(self_svc, rel_path, content)

    monkeypatch.setattr(VaultStorageService, "write_markdown_atomic", crash_once)

    with pytest.raises(OSError, match="Crash during move to 20-Projects"):
        api_client.put(
            f"/api/v1/notes/{note_id}",
            json={
                "title": "Collision Move Note",
                "note_type": "project",
                "body": "Staged updated body\n",
                "expected_hash": created["content_hash"],
            },
        )

    # Simulate an external unrelated file replacing 20-Projects/collision-move-note.md before recovery runs
    dest_file = settings.vault_dir / "20-Projects" / "collision-move-note.md"
    unrelated_content = "---\nid: \"99999999-9999-9999-9999-999999999999\"\ntitle: \"Unrelated File\"\n---\nDo not overwrite me!\n"
    dest_file.write_text(unrelated_content, encoding="utf-8")

    # Trigger runtime recovery via GET /api/v1/notes/{note_id}
    get_res = api_client.get(f"/api/v1/notes/{note_id}")
    assert get_res.status_code == 200

    # Verify unrelated file at dest_file was NOT overwritten!
    assert dest_file.read_text(encoding="utf-8") == unrelated_content
    # And our original note was safely recovered back to 10-Notes/collision-move-note.md with its staged content
    recovered = get_res.json()
    assert recovered["rel_path"] == "10-Notes/collision-move-note.md"
    assert recovered["body"] == "Staged updated body\n"

    # Now test tampered move journal with path traversal -> rejected and enters 503 degraded state
    evil_journal = settings.vault_dir / ".move-journal-evil.json"
    evil_journal.write_text(
        json.dumps(
            {
                "op_id": "evil",
                "src_rel_path": "10-Notes/../../outside.md",
                "dest_rel_path": "20-Projects/evil.md",
                "staged_filename": ".move-staged-evil.tmp",
                "staged_sha256": "a" * 64,
                "src_original_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )

    blocked_res = api_client.get("/api/v1/notes")
    assert blocked_res.status_code == 503
    assert blocked_res.json()["error"]["code"] == "RESTORE_IN_PROGRESS"

    health_res = api_client.get("/api/v1/system/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "degraded"

    # Cleanup evil journal so fixture teardown is clean
    evil_journal.unlink(missing_ok=True)
    maintenance_gate.reset_for_testing()


def test_external_disk_edit_reconciliation_and_get_concurrency(
    api_client: TestClient,
) -> None:
    """Gate 2 & P0-4: External disk edit auto-refresh on GET and concurrent GET + PATCH relocation safety."""
    created = api_client.post(
        "/api/v1/notes",
        json={
            "title": "External Edit Note",
            "note_type": "note",
            "body": "Initial disk body\n",
        },
    ).json()
    note_id = created["id"]
    md_path = settings.vault_dir / created["rel_path"]

    # Modify file directly on disk
    raw_disk = md_path.read_text(encoding="utf-8").replace(
        "Initial disk body\n", "Modified externally in Neovim\n"
    )
    md_path.write_text(raw_disk, encoding="utf-8")

    # GET /api/v1/notes/{id} detects hash mismatch and auto-reconciles SQLite + FTS5
    refreshed = api_client.get(f"/api/v1/notes/{note_id}").json()
    assert refreshed["body"] == "Modified externally in Neovim\n"
    assert refreshed["content_hash"] != created["content_hash"]

    # Verify FTS5 index was also updated synchronously
    search_res = api_client.get("/api/v1/search", params={"q": "Neovim"}).json()
    assert search_res["total_matches"] == 1
    assert search_res["results"][0]["id"] == note_id

    # Concurrency test: concurrent GETs and folder-relocating PATCH under db_write_lock
    current_hash = refreshed["content_hash"]

    def do_get() -> int:
        r = api_client.get(f"/api/v1/notes/{note_id}")
        return r.status_code

    def do_relocating_patch() -> int:
        r = api_client.patch(
            f"/api/v1/notes/{note_id}",
            json={
                "folder": "30-Experiments",
                "expected_hash": current_hash,
            },
        )
        return r.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(do_get) for _ in range(4)]
        futures.append(pool.submit(do_relocating_patch))
        statuses = [f.result() for f in futures]

    assert all(code == 200 for code in statuses)
    final_note = api_client.get(f"/api/v1/notes/{note_id}").json()
    assert final_note["folder"] == "30-Experiments"
    assert final_note["id"] == note_id
