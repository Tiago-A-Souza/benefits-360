"""Integração do fluxo ETAPA 2.4 + 2.5 via API."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repo = SQLiteStudyRepository(tmp_path / "fluxo.db")
    app = create_app(repo=repo)
    return TestClient(app)


def test_fluxo_demo_12_rascunho_pendencias_calcular(client: TestClient):
    res = client.get("/api/estudos/demo-12/rascunho")
    assert res.status_code == 200
    rascunho = res.json()
    assert rascunho["id"] == "demo-12"
    assert len(rascunho["opcoes_proposta"]) >= 1
    assert len(rascunho["cenarios"]) >= 1

    pend = client.get("/api/estudos/demo-12/pendencias")
    assert pend.status_code == 200
    bloqueios = [p for p in pend.json() if p["tipo"] == "bloqueio"]
    assert not bloqueios

    calc = client.post("/api/estudos/demo-12/calcular")
    assert calc.status_code == 200
    data = calc.json()
    assert data["calculo_realizado"] is True
    assert data["beneficiarios_calculados"] == 12
    assert data["totais"] is not None
    assert len(data["secoes"]) >= 1
    assert data["secoes"][0]["vidas"]
    for p in data["pendencias"]:
        assert "APP-" not in p["titulo"]
        assert "B-0" not in p["titulo"]


def test_pendencias_orientam_antes_do_calculo(client: TestClient):
    rascunho = rascunho_demo_12_vidas().model_dump(mode="json")
    copia = deepcopy(rascunho)
    copia["escolhas"]["data_referencia_idade"] = None
    client.put("/api/estudos/demo-12", json=copia)

    pend = client.get("/api/estudos/demo-12/pendencias").json()
    assert any(p["tipo"] == "bloqueio" for p in pend)
    assert any("idade" in p["titulo"].lower() or "idade" in p["descricao"].lower() for p in pend)

    calc = client.post("/api/estudos/demo-12/calcular")
    assert calc.status_code == 200
    body = calc.json()
    assert body["calculo_realizado"] is False
    assert any(b["codigo"] == "APP-ESC-001" for b in body["consistencia"]["bloqueios"])


def test_renovacao_dois_planos_e_duas_propostas(client: TestClient):
    rascunho = rascunho_demo_12_vidas().model_dump(mode="json")
    sg2 = deepcopy(rascunho["subgrupos_atuais"][0])
    sg2["id"] = "sg-2"
    sg2["plano_nome"] = "Plano atual B"
    rascunho["subgrupos_atuais"].append(sg2)

    for i, vida in enumerate(rascunho["vidas"]):
        if i >= len(rascunho["vidas"]) // 2:
            vida["subgrupo_atual_id"] = "sg-2"

    op2 = deepcopy(rascunho["opcoes_proposta"][0])
    op2["id"] = "op-2"
    op2["plano_nome"] = "Proposta B"
    op2["regime_copart_id"] = "regime-parcial"
    rascunho["opcoes_proposta"].append(op2)
    if not any(r["id"] == "regime-parcial" for r in rascunho["regimes_copart"]):
        rascunho["regimes_copart"].append({"id": "regime-parcial", "tipo": "parcial"})

    rascunho["cenarios"] = []

    put = client.put("/api/estudos/demo-12", json=rascunho)
    assert put.status_code == 200

    get = client.get("/api/estudos/demo-12/rascunho")
    body = get.json()
    assert len(body["cenarios"]) == 2
    for i, cenario in enumerate(body["cenarios"]):
        assert len(cenario["atribuicoes"]) == 2
        assert {a["alvo_id"] for a in cenario["atribuicoes"]} == {"sg-1", "sg-2"}

    calc = client.post("/api/estudos/demo-12/calcular")
    assert calc.status_code == 200
    data = calc.json()
    assert data["calculo_realizado"] is True
    assert len(data["propostas"]) == 2
    regimes = {p["regime_tipo"] for p in data["propostas"]}
    assert "sem" in regimes
    assert "parcial" in regimes
