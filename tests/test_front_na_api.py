"""A API serve o front compilado na mesma porta, sem interferir em /api."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.repository.sqlite import SQLiteStudyRepository


@pytest.fixture
def dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "dist"
    (pasta / "assets").mkdir(parents=True)
    (pasta / "index.html").write_text("<!doctype html><title>Benefits</title>", encoding="utf-8")
    (pasta / "assets" / "app.js").write_text("window.BENEFITS=1", encoding="utf-8")
    monkeypatch.setenv("NEWPORT_WEB_DIST", str(pasta))
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    return pasta


@pytest.fixture
def client(tmp_path: Path, dist: Path) -> TestClient:
    return TestClient(
        create_app(repo=SQLiteStudyRepository(tmp_path / "e.db"), seed_demos=False)
    )


def test_index_e_fallback_spa(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "Benefits" in r.text
    r2 = client.get("/estudos")
    assert r2.status_code == 200
    assert "Benefits" in r2.text
    r3 = client.get("/assets/app.js")
    assert r3.status_code == 200
    assert "BENEFITS" in r3.text


def test_api_nao_e_engolida_pelo_front(client: TestClient):
    saude = client.get("/api/saude")
    assert saude.status_code == 200
    assert saude.json() == {"ok": True}
    estudos = client.get("/api/estudos")
    assert estudos.status_code == 200
    assert estudos.json() == []
