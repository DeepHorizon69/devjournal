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


def test_taxonomy_and_dashboard_aggregations(api_client: TestClient) -> None:
    n1 = api_client.post(
        "/api/v1/notes",
        json={
            "title": "WireGuard Site-to-Site",
            "template_id": "troubleshooting",
            "domains": ["Networking", "Linux"],
            "tags": ["wireguard", "vpn"],
        },
    ).json()
    n2 = api_client.post(
        "/api/v1/notes",
        json={
            "title": "BBRv3 Throughput Lab",
            "template_id": "experiment",
            "domains": ["Networking"],
            "tags": ["tcp", "bbr"],
        },
    ).json()
    n3 = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Trashed Scratchpad",
            "template_id": "general",
            "domains": ["Programming"],
            "tags": ["scratch"],
        },
    ).json()
    api_client.delete(f"/api/v1/notes/{n3['id']}")

    tax = api_client.get("/api/v1/taxonomy").json()
    assert tax["total_active"] == 2
    assert tax["total_trashed"] == 1
    assert tax["types"]["troubleshooting"] == 1
    assert tax["types"]["experiment"] == 1
    assert tax["domains"]["Networking"] == 2
    assert tax["domains"]["Linux"] == 1
    assert tax["domains"]["Programming"] == 0
    assert tax["tags"]["wireguard"] == 1
    assert "scratch" not in tax["tags"]

    dash = api_client.get("/api/v1/dashboard").json()
    assert dash["counts"]["total_notes"] == 2
    assert dash["counts"]["troubleshooting"] == 1
    assert dash["counts"]["experiments"] == 1
    assert len(dash["recently_opened"]) == 2
    assert len(dash["recently_updated"]) == 2
    assert {item["id"] for item in dash["recently_updated"]} == {n1["id"], n2["id"]}


def test_search_collision_resistant_nonce_markers_and_literal_html_safety(
    api_client: TestClient,
) -> None:
    """P1-3 & Gate 6: Literal <mark>, </mark>, \\x01, \\x02, and <script> in note body never cause false highlights or XSS."""
    adversarial_body = (
        "Testing literal <mark>unmatched</mark> tags, control chars \x01 and \x02, "
        "and <script>alert('xss')</script> alongside the real target keyword wireguard.\n"
    )
    created = api_client.post(
        "/api/v1/notes",
        json={
            "title": "Adversarial Highlight Note",
            "note_type": "note",
            "domains": ["Cybersecurity"],
            "tags": ["security"],
            "body": adversarial_body,
        },
    ).json()
    md_path = settings.vault_dir / created["rel_path"]
    raw_before = md_path.read_text(encoding="utf-8")

    search_res = api_client.get("/api/v1/search", params={"q": "wireguard"})
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["total_matches"] == 1
    hit = data["results"][0]

    # 1. Verify structured snippet_segments ONLY highlights 'wireguard'
    highlighted_texts = [
        seg["text"].lower() for seg in hit["snippet_segments"] if seg["highlight"]
    ]
    assert highlighted_texts == ["wireguard"]

    non_highlighted_joined = "".join(
        seg["text"] for seg in hit["snippet_segments"] if not seg["highlight"]
    )
    assert "<mark>unmatched</mark>" in non_highlighted_joined
    assert "<script>alert('xss')</script>" in non_highlighted_joined

    # 2. Verify legacy snippet string escapes literal <mark> and <script> while wrapping only the matched token
    assert "&lt;mark&gt;unmatched&lt;/mark&gt;" in hit["snippet"]
    assert "&lt;script&gt;" in hit["snippet"]
    assert "<mark>wireguard</mark>" in hit["snippet"].lower()

    # 3. Verify canonical Markdown file on disk is completely unmodified
    assert md_path.read_text(encoding="utf-8") == raw_before

    # 4. Verify FTS5 syntax edge cases never raise 500
    for tricky_query in (
        '"unclosed quote',
        "foo:bar:baz",
        "AND OR NOT NEAR",
        "*** ^^^ ((( ))) ---",
        "   ",
    ):
        r = api_client.get("/api/v1/search", params={"q": tricky_query})
        assert r.status_code == 200
