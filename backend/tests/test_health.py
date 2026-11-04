from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient
from app.config import settings
from app.db.connection import init_db
from app.main import app
from app.services.vault_storage import VaultStorageService


@pytest.mark.asyncio
async def test_health_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path / "devjournal-data")
    settings.ensure_directories()
    VaultStorageService(settings.vault_dir).ensure_vault_structure()
    init_db(settings.db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["vault_writable"] is True
        assert data["db_ok"] is True
        assert isinstance(data["indexed_notes"], int)
        assert list(settings.vault_dir.glob(".health_check_*")) == []


@pytest.mark.asyncio
async def test_spa_serving() -> None:
    if not (
        settings.frontend_dist_dir
        and (settings.frontend_dist_dir / "index.html").exists()
    ):
        pytest.skip("frontend/dist not built")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower()
        assert "DevJournal" in response.text


@pytest.mark.asyncio
async def test_lifespan_startup_initializes_vault_db_and_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import lifespan

    monkeypatch.setattr(settings, "data_dir", tmp_path / "lifespan-data")
    # Pre-seed an external markdown file before startup lifespan runs
    inbox_dir = settings.vault_dir / "00-Inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    (inbox_dir / "startup-seed.md").write_text(
        "# Seeded Before Lifespan\n\nIndexed automatically on startup.\n",
        encoding="utf-8",
    )

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/system/health")
            assert resp.status_code == 200
            body = resp.json()
            assert body["status"] == "ok"
            assert body["indexed_notes"] == 1

            not_found = await client.get("/api/v1/nonexistent-endpoint")
            assert not_found.status_code == 404
