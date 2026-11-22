"""Aba Cotações no Benefits: ponte com o RPA local (sem dados de estudo)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.services.rpa_cotacoes import AVISO_IFRAME_HOSPEDADO


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(seed_demos=False))


def test_rpa_cotacoes_estado_ligado(client: TestClient):
    with patch(
        "newport_app.api.main.rpa_cotacoes_svc.consultar_estado_tela_rpa",
        return_value={
            "ligado": True,
            "url": "http://127.0.0.1:8600",
            "estado": {"simulador": True},
        },
    ):
        r = client.get("/api/rpa-cotacoes/estado")
    assert r.status_code == 200
    body = r.json()
    assert body["ligado"] is True
    assert body["url"] == "http://127.0.0.1:8600"
    assert body["estado"]["simulador"] is True
    assert body.get("comando_subir") is None


def test_rpa_cotacoes_estado_desligado_traz_comando(client: TestClient):
    cmd = r"powershell -ExecutionPolicy Bypass -File .\scripts\subir-benefits-e-rpa.ps1"
    with patch(
        "newport_app.api.main.rpa_cotacoes_svc.consultar_estado_tela_rpa",
        return_value={"ligado": False, "url": "http://127.0.0.1:8600", "comando_subir": cmd},
    ):
        r = client.get("/api/rpa-cotacoes/estado")
    assert r.status_code == 200
    body = r.json()
    assert body["ligado"] is False
    assert "subir-benefits-e-rpa" in body["comando_subir"]


def test_rpa_cotacoes_estado_hospedado_nao_consulta_localhost(client: TestClient, monkeypatch):
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    with patch(
        "newport_app.services.rpa_cotacoes.urllib.request.urlopen",
        side_effect=AssertionError("não deve consultar o robô no servidor"),
    ):
        r = client.get("/api/rpa-cotacoes/estado")
    assert r.status_code == 200
    body = r.json()
    assert body["ligado"] is False
    assert body["hospedado"] is True
    assert AVISO_IFRAME_HOSPEDADO in body["aviso"]
    assert body.get("comando_subir") is None