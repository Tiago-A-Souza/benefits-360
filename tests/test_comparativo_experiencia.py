"""Tela 5 — seleção para apresentação, campos numéricos e snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.adapters.motor_out import motor_result_para_comparativo
from newport_app.draft_compiler import compile
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.comparativo_ui import salvar_selecao_apresentacao
from newport_motor.engine import calcular
from tests.test_comparativo_multiplas_propostas import _rascunho_quatro_propostas


def test_propostas_tem_campos_numericos_e_faixas():
    rascunho = _rascunho_quatro_propostas()
    compilado = compile(rascunho)
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    resp = motor_result_para_comparativo(rascunho, motor)

    assert resp.planos_atuais
    assert resp.planos_atuais[0].mensal_centavos is not None

    for p in resp.propostas:
        assert p.numerico is not None
        assert p.numerico.proposta_mensal_centavos is not None
        assert p.numerico.atual_mensal_centavos is not None
        assert p.numerico.diff_mes_centavos is not None
        assert p.numerico.diff_bps is not None

    faixas = resp.planos_atuais[0].faixas
    assert faixas
    for fx in faixas:
        assert fx.quantidade > 0
        assert fx.propostas

    destaques = {d for p in resp.propostas for d in p.destaques}
    assert "menor_mensalidade" in destaques
    assert "mais_proximo_atual" in destaques


def test_filtro_grupo_regime_quatro_propostas():
    rascunho = _rascunho_quatro_propostas()
    compilado = compile(rascunho)
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    resp = motor_result_para_comparativo(rascunho, motor)

    sem = [p for p in resp.propostas if p.grupo_regime == "sem_copart"]
    com = [p for p in resp.propostas if p.grupo_regime == "com_copart"]
    assert len(sem) == 2
    assert len(com) == 2


def test_salvar_selecao_apresentacao_persiste_ordem():
    rascunho = _rascunho_quatro_propostas()
    resp = salvar_selecao_apresentacao(rascunho, ["op-3", "op-1", "op-3"])
    assert resp.ordem == ["op-3", "op-1"]
    assert rascunho.selecao_apresentacao is not None
    assert rascunho.selecao_apresentacao.ordem == ["op-3", "op-1"]


@pytest.fixture
def client(tmp_path: Path):
    db = tmp_path / "cmp_exp.db"
    repo = SQLiteStudyRepository(db)
    from newport_app.api.main import create_app

    return TestClient(create_app(repo=repo)), repo


def test_api_selecao_apresentacao_e_snapshot(client):
    test_client, repo = client
    rascunho = _rascunho_quatro_propostas()
    repo.salvar_rascunho(rascunho)

    res = test_client.put(
        "/api/estudos/test-4-propostas/comparativo/selecao-apresentacao",
        json={"opcao_ids": ["op-2", "op-4"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ordem"] == ["op-2", "op-4"]

    rascunho_atual = repo.obter_rascunho("test-4-propostas")
    assert rascunho_atual.selecao_apresentacao.ordem == ["op-2", "op-4"]

    calc = test_client.post("/api/estudos/test-4-propostas/calcular")
    assert calc.status_code == 200
    assert calc.json()["propostas_apresentacao"] == ["op-2", "op-4"]

    snap_res = test_client.post("/api/estudos/test-4-propostas/snapshot")
    assert snap_res.status_code == 200
    snap_id = snap_res.json()["snapshot_id"]
    snap_get = test_client.get(f"/api/estudos/test-4-propostas/snapshots/{snap_id}")
    assert snap_get.status_code == 200
    snap = snap_get.json()
    assert snap["payload"]["propostas_apresentacao"] == ["op-2", "op-4"]
