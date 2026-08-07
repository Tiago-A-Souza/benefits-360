"""Comparativo expõe erros de compilação na etapa 5."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import PriceBasisRascunho
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_motor.engine import calcular
from newport_motor.result import MotorResult
from newport_motor.types import SeveridadeValidacao
from tests.test_comparativo_multiplas_propostas import _rascunho_quatro_propostas


def _calcular_via_servico(rascunho, repo):
    repo.salvar_rascunho(rascunho)
    return CalculoService(repo).calcular(rascunho.id)


def test_app_esc_001_sem_data_referencia_visivel_no_comparativo(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "esc001.db")
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.data_referencia_idade = None

    resp = _calcular_via_servico(rascunho, repo)

    assert resp.calculo_realizado is False
    assert resp.consistencia is not None
    assert resp.consistencia.consistente is False
    bloqueios = [b for b in resp.consistencia.bloqueios if b.codigo == "APP-ESC-001"]
    assert bloqueios
    assert bloqueios[0].origem == "compilacao"
    assert bloqueios[0].mensagem
    assert bloqueios[0].alvo_rotulo == "Data de referência para idades"
    assert bloqueios[0].etapa_sugerida == 2
    assert "APP-ESC-001" in (resp.consistencia.mensagem or "")


def test_app_fin_001_price_basis_desconhecido_indica_proposta(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "fin001.db")
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].tabela[0].price_basis = PriceBasisRascunho.DESCONHECIDO

    resp = _calcular_via_servico(rascunho, repo)

    bloqueios = [b for b in resp.consistencia.bloqueios if b.codigo == "APP-FIN-001"]
    assert bloqueios
    assert bloqueios[0].origem == "compilacao"
    assert "Proposta fictícia" in (bloqueios[0].alvo_rotulo or "")
    assert "base IOF" in (bloqueios[0].alvo_rotulo or "")
    assert bloqueios[0].etapa_sugerida == 3


def test_app_esc_002_baseline_nao_confirmado_visivel(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "esc002.db")
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.baseline_escolhido.confirmado = False

    resp = _calcular_via_servico(rascunho, repo)

    bloqueios = [b for b in resp.consistencia.bloqueios if b.codigo == "APP-ESC-002"]
    assert bloqueios
    assert bloqueios[0].alvo_rotulo == "Comparação do plano atual"


def test_compilacao_e_motor_agrupados_por_origem():
    rascunho = rascunho_demo_12_vidas()
    erros = [
        ErroCompilacao(
            codigo="APP-ESC-001",
            caminho="/escolhas/data_referencia_idade",
            mensagem="Informe a data de referência para calcular as idades do estudo.",
        )
    ]
    motor = MotorResult(
        estudo_id=rascunho.id,
        validacoes=[
            {
                "codigo": "B-06",
                "severidade": SeveridadeValidacao.BLOQUEANTE,
                "mensagem": "Alvo sg-1 sem atribuição no cenário c1.",
                "alvo_ref": "cenario:c1:alvo:sg-1",
            }
        ],
    )

    resp = montar_comparativo(rascunho, motor_result=motor, erros_compilacao=erros)

    origens = {b.origem for b in resp.consistencia.bloqueios}
    assert origens == {"compilacao", "motor"}
    assert any(b.codigo == "APP-ESC-001" for b in resp.consistencia.bloqueios)
    assert any(b.codigo == "B-06" for b in resp.consistencia.bloqueios)


def test_estudo_valido_sem_regressao(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "ok.db")
    rascunho = _rascunho_quatro_propostas()
    resp = _calcular_via_servico(rascunho, repo)

    assert resp.calculo_realizado is True
    assert resp.consistencia is not None
    assert resp.consistencia.consistente is True
    assert resp.consistencia.bloqueios == []


@pytest.fixture
def client(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "api.db")
    from newport_app.api.main import create_app

    return TestClient(create_app(repo=repo)), repo


def test_api_calcular_incompleto_retorna_comparativo_com_bloqueios(client):
    test_client, repo = client
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.baseline_escolhido.confirmado = False
    repo.salvar_rascunho(rascunho)

    res = test_client.post("/api/estudos/demo-12/calcular")
    assert res.status_code == 200
    body = res.json()
    assert body["calculo_realizado"] is False
    assert any(b["codigo"] == "APP-ESC-002" for b in body["consistencia"]["bloqueios"])
