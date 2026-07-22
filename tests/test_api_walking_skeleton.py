"""Testes de integração — walking skeleton ETAPA 2.1."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.calculo import CalculoService


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "test.db"
    repo = SQLiteStudyRepository(db)
    app = create_app(repo=repo)
    return TestClient(app)


def test_listar_estudos_demo(client: TestClient):
    res = client.get("/api/estudos")
    assert res.status_code == 200
    ids = res.json()
    assert "demo-12" in ids
    assert "demo-41" in ids


def test_resumo_demo_12(client: TestClient):
    res = client.get("/api/estudos/demo-12")
    assert res.status_code == 200
    data = res.json()
    assert data["beneficiarios_incluidos"] == 12
    assert "fictício" in data["descricao"].lower() or "fictíc" in data["descricao"].lower()


def test_calcular_demo_12_integracao_motor(client: TestClient):
    res = client.post("/api/estudos/demo-12/calcular")
    assert res.status_code == 200
    data = res.json()
    assert data["calculo_realizado"] is True
    assert data["beneficiarios_calculados"] == 12
    assert data["totais"] is not None
    assert data["totais"]["proposta_mensal_reais"].startswith("R$")
    assert "diferenca_mensal_reais" in data["totais"]
    assert "diferenca_anual_reais" in data["totais"]
    bloqueios = [p for p in data["pendencias"] if p["tipo"] == "bloqueio"]
    assert not bloqueios
    h01 = [p for p in data["pendencias"] if "homologada" in p["titulo"].lower()]
    assert not h01
    codigos = {a["codigo"] for a in data["auditoria"]}
    assert "H-01" not in codigos


def test_calcular_demo_41_sem_truncar_com_h01(client: TestClient):
    res = client.post("/api/estudos/demo-41/calcular")
    assert res.status_code == 200
    data = res.json()
    assert data["calculo_realizado"] is True
    assert data["beneficiarios_calculados"] == 41
    alertas = [p for p in data["pendencias"] if p["tipo"] == "alerta"]
    assert len(alertas) >= 1
    assert any("homologada" in a["titulo"].lower() for a in alertas)
    assert any(a["codigo"] == "H-01" for a in data["auditoria"])
    bloqueios = [p for p in data["pendencias"] if p["tipo"] == "bloqueio"]
    assert not bloqueios


def test_repositorio_preserva_todas_as_vidas(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "r.db")
    service = CalculoService(repo)
    r41 = rascunho_demo_41_vidas()
    service.garantir_rascunho(r41)
    carregado = repo.obter_rascunho("demo-41")
    assert carregado is not None
    assert len(carregado.vidas) == 41
    assert len(carregado.vidas_incluidas()) == 41


def test_zero_vidas_bloqueia(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "z.db")
    service = CalculoService(repo)
    r = rascunho_demo_12_vidas()
    for v in r.vidas:
        v.incluida = False
    service.garantir_rascunho(r)
    out = service.calcular("demo-12")
    assert out.calculo_realizado is False
    assert any(p.tipo == "bloqueio" for p in out.pendencias)


def test_resposta_nao_expoe_termos_internos_como_titulo(client: TestClient):
    res = client.post("/api/estudos/demo-12/calcular")
    texto = res.text
    for termo in ("EstudoInput", "EffectivePolicy", "price_basis"):
        assert termo not in texto
    pend = res.json()["pendencias"]
    for p in pend:
        assert "B-08" not in p["titulo"]
        assert "H-01" not in p["titulo"]
