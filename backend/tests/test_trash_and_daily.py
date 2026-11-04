from __future__ import annotations

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


def test_trash_first_permanent_deletion_and_restore_lifecycle(
    api_client: TestClient,
) -> None:
    """Gate 4 & P0-2: Active notes cannot be permanently deleted directly; must go Active -> Trash -> Permanent Delete."""
    created = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Protected Active Note",
            "note_type": "note",
            "body": "Must not be permanently deleted while active\n",
        },
    ).json()
    note_id = created["id"]
    orig_rel_path = created["rel_path"]

    # 1. Direct permanent delete on active note -> 400 INVALID_TRASH_OPERATION
    direct_perm = api_client.delete(
        f"/api/v1/notes/{note_id}", params={"permanent": True}
    )
    assert direct_perm.status_code == 400
    assert direct_perm.json()["error"]["code"] == "INVALID_TRASH_OPERATION"
    assert (settings.vault_dir / orig_rel_path).is_file()

    # 2. Soft delete to Trash -> 200 OK
    soft_del = api_client.delete(f"/api/v1/notes/{note_id}")
    assert soft_del.status_code == 200
    assert soft_del.json() == {
        "status": "ok",
        "deleted_id": note_id,
        "permanent": False,
    }
    assert not (settings.vault_dir / orig_rel_path).exists()
    assert (settings.vault_dir / "99-Trash" / "protected-active-note.md").is_file()

    # 3. Restore from Trash -> 200 OK back to original path
    restored = api_client.post(f"/api/v1/notes/{note_id}/restore")
    assert restored.status_code == 200
    restored_data = restored.json()
    assert restored_data["is_trashed"] is False
    assert restored_data["rel_path"] == orig_rel_path
    assert (settings.vault_dir / orig_rel_path).is_file()

    # 4. Soft delete again, then permanent delete from Trash -> 200 OK
    api_client.delete(f"/api/v1/notes/{note_id}")
    perm_del = api_client.delete(
        f"/api/v1/notes/{note_id}", params={"permanent": True}
    )
    assert perm_del.status_code == 200
    assert perm_del.json() == {
        "status": "ok",
        "deleted_id": note_id,
        "permanent": True,
    }
    assert not (settings.vault_dir / "99-Trash" / "protected-active-note.md").exists()
    assert api_client.get(f"/api/v1/notes/{note_id}").status_code == 404


def test_unbounded_empty_trash_over_100_notes_plus_orphan_files(
    api_client: TestClient,
) -> None:
    """Gate 4: Verify DELETE /api/v1/notes/trash deletes >100 trashed notes and unindexed orphan files."""
    for i in range(105):
        n = api_client.post(
            "/api/v1/notes",
            json={"title": f"Trash Item {i:03d}", "body": f"Body {i}\n"},
        ).json()
        api_client.delete(f"/api/v1/notes/{n['id']}")

    # Also write an unindexed orphan .md file directly in 99-Trash/
    orphan_path = settings.vault_dir / "99-Trash" / "orphan-unindexed.md"
    orphan_path.write_text("# Orphan\n", encoding="utf-8")

    empty_res = api_client.delete("/api/v1/notes/trash")
    assert empty_res.status_code == 200
    assert empty_res.json()["deleted_count"] == 106

    trashed_list = api_client.get("/api/v1/notes", params={"trashed": True}).json()
    assert trashed_list["total"] == 0
    assert list((settings.vault_dir / "99-Trash").glob("*.md")) == []


def test_daily_journal_idempotency_timezone_and_calendar_validation(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gate 4 & P1-6: Verify daily journal creation, idempotency, timezone config, and invalid calendar date rejection."""
    # 1. Explicit valid date -> first call 201 Created, second call 200 OK
    first_res = api_client.post(
        "/api/v1/notes/daily/today", json={"date": "2026-11-04"}
    )
    assert first_res.status_code == 201
    first_data = first_res.json()
    assert first_data["title"] == "2026-11-04"
    assert first_data["rel_path"] == "90-Daily/2026-11-04.md"
    assert first_data["note_type"] == "daily"
    assert first_data["status"] == "active"

    second_res = api_client.post(
        "/api/v1/notes/daily/today", json={"date": "2026-11-04"}
    )
    assert second_res.status_code == 200
    assert second_res.json()["id"] == first_data["id"]

    # 2. Invalid calendar dates -> 400 INVALID_DATE
    for bad_date in ("2026-02-30", "2026-13-01", "not-a-date", "2026/11/04"):
        bad_res = api_client.post(
            "/api/v1/notes/daily/today", json={"date": bad_date}
        )
        assert bad_res.status_code == 400
        assert bad_res.json()["error"]["code"] == "INVALID_DATE"

    # 3. Invalid timezone setting gracefully falls back to UTC
    monkeypatch.setattr(settings, "timezone", "Invalid/Timezone_Name")
    today_res = api_client.post("/api/v1/notes/daily/today")
    assert today_res.status_code in (200, 201)
    assert today_res.json()["folder"] == "90-Daily"
