"""Regressão — comparativo com múltiplas propostas (tela 5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.adapters.motor_out import motor_result_para_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    OpcaoPropostaRascunho,
    RegimeCopartRascunho,
    TabelaFaixaRascunho,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_motor.engine import calcular


def _rascunho_quatro_propostas():
    base = rascunho_demo_12_vidas()
    vidas = base.vidas[:3]
    template = base.opcoes_proposta[0]

    def _tabela(delta: int) -> list[TabelaFaixaRascunho]:
        return [
            TabelaFaixaRascunho(
                faixa=f.faixa,
                valor_centavos=f.valor_centavos + delta,
                quantidade_cotada=f.quantidade_cotada,
                price_basis=f.price_basis,
                proveniencia=f.proveniencia,
            )
            for f in template.tabela
        ]

    specs = [
        ("op-1", "DIAMANTE PRO Q", "regime-sem", 0),
        ("op-2", "OURO MAIS I Q", "regime-sem", 25_000),
        ("op-3", "DIAMANTE PRO COPAR Q", "regime-parcial", 50_000),
        ("op-4", "OURO MAIS I Q COPAR", "regime-parcial", 75_000),
    ]
    opcoes: list[OpcaoPropostaRascunho] = []
    cenarios: list[CenarioRascunho] = []
    for i, (op_id, nome, regime_id, delta) in enumerate(specs):
        opcoes.append(
            template.model_copy(
                update={
                    "id": op_id,
                    "plano_nome": nome,
                    "regime_copart_id": regime_id,
                    "tabela": _tabela(delta),
                }
            )
        )
        cenarios.append(
            CenarioRascunho(
                id=f"c{i + 1}",
                rotulo=nome,
                atribuicoes=[
                    AtribuicaoRascunho(
                        id=f"a{i + 1}",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-1",
                        opcao_plano_id=op_id,
                    )
                ],
            )
        )

    return base.model_copy(
        update={
            "id": "test-4-propostas",
            "titulo": "Comparativo 4 propostas",
            "vidas": vidas,
            "opcoes_proposta": opcoes,
            "regimes_copart": [
                RegimeCopartRascunho(id="regime-sem", tipo="sem"),
                RegimeCopartRascunho(id="regime-parcial", tipo="parcial"),
            ],
            "cenarios": cenarios,
        }
    )


def test_comparativo_quatro_propostas_motor_out():
    rascunho = _rascunho_quatro_propostas()
    compilado = compile(rascunho)
    assert compilado.compilavel
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    assert len(motor.cenarios) == 4

    resp = motor_result_para_comparativo(rascunho, motor)
    assert resp.consistencia is not None
    assert resp.consistencia.consistente is True
    assert resp.consistencia.propostas_selecionadas == 4
    assert resp.consistencia.cenarios_configurados == 4
    assert resp.consistencia.resultados_apresentados == 4
    assert len(resp.propostas) == 4
    assert resp.calculo_realizado is True

    nomes = {p.plano_nome for p in resp.propostas}
    assert nomes == {
        "DIAMANTE PRO Q",
        "OURO MAIS I Q",
        "DIAMANTE PRO COPAR Q",
        "OURO MAIS I Q COPAR",
    }

    grupos = {p.grupo_regime for p in resp.propostas}
    assert grupos == {"sem_copart", "com_copart"}

    totais = [p.totais.proposta_mensal_reais for p in resp.propostas if p.totais]
    assert len(totais) == 4
    assert len(set(totais)) == 4

    for proposta in resp.propostas:
        assert proposta.calculo_realizado
        assert proposta.totais is not None
        assert proposta.diferenca_percentual
        assert proposta.secoes
        assert proposta.secoes[0].vidas


def test_comparativo_menos_cenarios_que_propostas_calcula():
    """Etapa 4 manual: 4 propostas na etapa 3 e 2 cenários completos — válido."""
    rascunho = _rascunho_quatro_propostas()
    rascunho.cenarios = rascunho.cenarios[:2]
    compilado = compile(rascunho)
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    resp = motor_result_para_comparativo(rascunho, motor)
    assert resp.consistencia is not None
    assert resp.consistencia.consistente is True
    assert resp.calculo_realizado is True
    assert len(resp.propostas) == 2
    assert resp.consistencia.cenarios_configurados == 2
    assert resp.consistencia.propostas_selecionadas == 4
    assert not any(p.codigo == "APP-CMP-001" for p in resp.pendencias)
    # Alerta informativo: 2 propostas da etapa 3 ficaram fora (1 plano → sync
    # não se aplica; aqui 1 subgrupo, então APP-ET4-002 não dispara).
    assert len(rascunho.subgrupos_atuais) == 1


@pytest.fixture
def client(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "cmp.db")
    from newport_app.api.main import create_app

    return TestClient(create_app(repo=repo)), repo


def test_api_calcular_retorna_quatro_propostas(client):
    test_client, repo = client
    rascunho = _rascunho_quatro_propostas()
    repo.salvar_rascunho(rascunho)

    svc = CalculoService(repo)
    resp = svc.calcular("test-4-propostas")

    assert len(resp.propostas) == 4
    assert resp.consistencia is not None
    assert resp.consistencia.consistente is True
    assert resp.calculo_realizado is True

    res = test_client.post("/api/estudos/test-4-propostas/calcular")
    assert res.status_code == 200
    body = res.json()
    assert len(body["propostas"]) == 4
    assert body["consistencia"]["consistente"] is True
    assert body["calculo_realizado"] is True
    assert len({p["totais"]["proposta_mensal_reais"] for p in body["propostas"]}) == 4
