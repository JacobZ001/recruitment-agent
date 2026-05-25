from __future__ import annotations

from fastapi.testclient import TestClient

from integrations.api.app import create_app


def test_default_sqlite_db_is_recreated_for_clean_local_boot(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("VERTICAL_SLICE_ENV_FILE", str(env_file))
    monkeypatch.delenv("VERTICAL_SLICE_DB_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    db_path = tmp_path / "data" / "app.db"
    assert not db_path.exists()

    with TestClient(create_app()) as client:
        response = client.get("/health")
        reset_response = client.post("/admin/reset")

    assert response.status_code == 200
    assert response.json()["runtime"] == "vertical_slice_sqlite_sync"
    assert reset_response.status_code == 200
    assert db_path.exists()
