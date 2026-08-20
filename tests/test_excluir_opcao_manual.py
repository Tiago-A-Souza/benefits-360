"""Exclusão de cotação manual: governança no backend, não no React."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    ConfirmacaoComparativoRascunho,
    OpcaoPropostaRascunho,
    RegimeCopartRascunho,
    SelecaoApresentacaoRascunho,
    SubgrupoAtualRascunho,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.calculo import CalculoService
from newport_app.services.comparativo_confirmacao import rascunho_fingerprint_calc
from newport_app.services.opcao_proposta import (
    OpcaoPropostaDeExtracaoError,
    excluir_opcao_proposta_manual,
)
from newport_app.siscor_mapper.apply import rascunho_vazio


def _agora():
    return datetime.now(timezone.utc)


def _rascunho_base():
    rascunho = rascunho_vazio("est-exc-manual", "Exclusão manual")
    rascunho.regimes_copart.append(RegimeCopartRascunho(id="regime-sem", tipo="sem"))
    rascunho.subgrupos_atuais.append(
        SubgrupoAtualRascunho(id="sg-1", operadora="X", plano_nome="Atual")
    )
    rascunho.opcoes_proposta.extend(
        [
            OpcaoPropostaRascunho(
                id="op-man-1",
                operadora="X",
                plano_nome="Manual um",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
            ),
            OpcaoPropostaRascunho(
                id="op-man-2",
                operadora="X",
                plano_nome="Manual dois",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
            ),
            OpcaoPropostaRascunho(
                id="op-pdf",
                operadora="Porto",
                plano_nome="Importada",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
                extracao_id="ext-1",
            ),
        ]
    )
    rascunho.cenarios.extend(
        [
            CenarioRascunho(
                id="cen-1",
                rotulo="Manual um",
                atribuicoes=[
                    AtribuicaoRascunho(
                        id="atr-1",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-1",
                        opcao_plano_id="op-man-1",
                    )
                ],
            ),
            CenarioRascunho(
                id="cen-2",
                rotulo="Manual dois",
                atribuicoes=[
                    AtribuicaoRascunho(
                        id="atr-2",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-1",
                        opcao_plano_id="op-man-2",
                    )
                ],
            ),
            CenarioRascunho(
                id="cen-3",
                rotulo="Importada",
                atribuicoes=[
                    AtribuicaoRascunho(
                        id="atr-3",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-1",
                        opcao_plano_id="op-pdf",
                    )
                ],
            ),
        ]
    )
    sincronizar_cenarios(rascunho)
    rascunho.selecao_apresentacao = SelecaoApresentacaoRascunho(
        opcao_ids=["op-man-1", "op-pdf", "op-man-2"],
        ordem=["op-man-1", "op-pdf", "op-man-2"],
    )
    rascunho.confirmacao_comparativo = ConfirmacaoComparativoRascunho(
        opcao_ids=["op-man-1", "op-pdf", "op-man-2"],
        ordem=["op-man-1", "op-pdf", "op-man-2"],
        hash_comparativo="hash-gravado",
        rascunho_fingerprint=rascunho_fingerprint_calc(rascunho),
        confirmado_em=_agora(),
    )
    return rascunho


@pytest.fixture
def repo(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "exc-manual.db")


@pytest.fixture
def service(repo: SQLiteStudyRepository) -> CalculoService:
    return CalculoService(repo)


@pytest.fixture
def client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def test_excluir_manual_invalida_confirmacao_gravada(service: CalculoService, repo):
    rascunho = _rascunho_base()
    repo.salvar_rascunho(rascunho)
    assert repo.obter_rascunho(rascunho.id).confirmacao_comparativo is not None

    depois = service.excluir_opcao_proposta_manual(rascunho.id, "op-man-1")

    assert depois.confirmacao_comparativo is None
    assert repo.obter_rascunho(rascunho.id).confirmacao_comparativo is None


def test_excluir_manual_remove_id_de_selecao_apresentacao(service: CalculoService, repo):
    rascunho = _rascunho_base()
    repo.salvar_rascunho(rascunho)

    depois = service.excluir_opcao_proposta_manual(rascunho.id, "op-man-1")

    assert depois.selecao_apresentacao is not None
    assert depois.selecao_apresentacao.opcao_ids == ["op-pdf", "op-man-2"]
    assert depois.selecao_apresentacao.ordem == ["op-pdf", "op-man-2"]
    assert "op-man-1" not in depois.selecao_apresentacao.opcao_ids
    assert "op-man-1" not in depois.selecao_apresentacao.ordem


def test_excluir_manual_remove_atribuicoes_nos_cenarios():
    rascunho = _rascunho_base()
    excluir_opcao_proposta_manual(rascunho, "op-man-1")

    ids = [a.opcao_plano_id for c in rascunho.cenarios for a in c.atribuicoes]
    assert "op-man-1" not in ids
    assert "op-man-2" in ids
    assert "op-pdf" in ids
    assert {op.id for op in rascunho.opcoes_proposta} == {"op-man-2", "op-pdf"}


def test_excluir_cotacao_de_extracao_e_rejeitada(service: CalculoService, repo, client):
    rascunho = _rascunho_base()
    repo.salvar_rascunho(rascunho)

    with pytest.raises(OpcaoPropostaDeExtracaoError):
        excluir_opcao_proposta_manual(rascunho, "op-pdf")

    res = client.delete(f"/api/estudos/{rascunho.id}/opcoes-proposta/op-pdf")
    assert res.status_code == 409
    depois = repo.obter_rascunho(rascunho.id)
    assert {op.id for op in depois.opcoes_proposta} == {"op-man-1", "op-man-2", "op-pdf"}
    assert depois.confirmacao_comparativo is not None


def test_excluir_ultima_cotacao_manual_nao_quebra_selecao(service: CalculoService, repo):
    rascunho = _rascunho_base()
    rascunho.opcoes_proposta = [
        op for op in rascunho.opcoes_proposta if op.id != "op-man-2"
    ]
    sincronizar_cenarios(rascunho)
    rascunho.selecao_apresentacao = SelecaoApresentacaoRascunho(
        opcao_ids=["op-man-1"],
        ordem=["op-man-1"],
    )
    rascunho.confirmacao_comparativo = ConfirmacaoComparativoRascunho(
        opcao_ids=["op-man-1"],
        ordem=["op-man-1"],
        hash_comparativo="hash-gravado",
        rascunho_fingerprint=rascunho_fingerprint_calc(rascunho),
        confirmado_em=_agora(),
    )
    repo.salvar_rascunho(rascunho)

    depois = service.excluir_opcao_proposta_manual(rascunho.id, "op-man-1")

    assert {op.id for op in depois.opcoes_proposta} == {"op-pdf"}
    assert depois.selecao_apresentacao is None
    assert depois.confirmacao_comparativo is None
    ids = [a.opcao_plano_id for c in depois.cenarios for a in c.atribuicoes]
    assert "op-man-1" not in ids


def test_salvar_rascunho_limpa_orfos_da_selecao_mesmo_sem_o_endpoint(repo):
    """Rede de segurança: PUT genérico também não persiste id órfão."""
    rascunho = _rascunho_base()
    rascunho.opcoes_proposta = [
        op for op in rascunho.opcoes_proposta if op.id != "op-man-1"
    ]
    repo.salvar_rascunho(rascunho)
    depois = repo.obter_rascunho(rascunho.id)
    assert depois.selecao_apresentacao is not None
    assert "op-man-1" not in depois.selecao_apresentacao.opcao_ids
    assert "op-man-1" not in depois.selecao_apresentacao.ordem
    assert depois.selecao_apresentacao.ordem == ["op-pdf", "op-man-2"]
    assert depois.confirmacao_comparativo is None
