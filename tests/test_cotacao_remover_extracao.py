"""Remoção de extração PDF limpa opções e atribuições de cenário."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.config.paths import caminho_banco_cotacoes, caminho_banco_estudos
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    DocumentoCotacaoRascunho,
    OpcaoPropostaRascunho,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
)
from newport_app.siscor_mapper.apply import rascunho_vazio
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.extracao_cotacao import ExtracaoCotacaoService


def test_remover_extracao_remove_atribuicoes_orfas(tmp_path, monkeypatch):
    estudos_path = tmp_path / "estudos.db"
    cotacoes_path = tmp_path / "cotacoes.db"
    monkeypatch.setattr(
        "newport_app.config.paths.caminho_banco_estudos",
        lambda modo=None: estudos_path,
    )
    monkeypatch.setattr(
        "newport_app.config.paths.caminho_banco_cotacoes",
        lambda modo=None: cotacoes_path,
    )

    estudos = SQLiteStudyRepository(estudos_path)
    extracoes = ExtracaoCotacaoRepository(cotacoes_path)
    svc = ExtracaoCotacaoService(estudos, extracoes)

    estudo_id = "est-rem"
    rascunho = rascunho_vazio(estudo_id, "Teste")
    rascunho.regimes_copart.append(RegimeCopartRascunho(id="regime-sem", tipo="sem"))
    rascunho.subgrupos_atuais.extend(
        [
            SubgrupoAtualRascunho(id="sg-1", operadora="X", plano_nome="A"),
            SubgrupoAtualRascunho(id="sg-2", operadora="X", plano_nome="B"),
        ]
    )
    rascunho.documentos_cotacao.append(
        DocumentoCotacaoRascunho(id="doc-1", operadora="Porto", hash="h")
    )
    rascunho.opcoes_proposta.append(
        OpcaoPropostaRascunho(
            id="op-manter",
            operadora="X",
            plano_nome="Manter",
            regime_copart_id="regime-sem",
            tipo_fiscal="seguradora",
            extracao_id="ext-outra",
            documento_cotacao_id=None,
        )
    )
    rascunho.opcoes_proposta.append(
        OpcaoPropostaRascunho(
            id="op-remover",
            operadora="Porto",
            plano_nome="Remover",
            regime_copart_id="regime-sem",
            tipo_fiscal="seguradora",
            extracao_id="ext-remover",
            documento_cotacao_id="doc-1",
        )
    )
    rascunho.cenarios.append(
        CenarioRascunho(
            id="cen-1",
            nome="Cenário",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="atr-1",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-1",
                    opcao_plano_id="op-remover",
                ),
                AtribuicaoRascunho(
                    id="atr-2",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-2",
                    opcao_plano_id="op-manter",
                ),
            ],
        )
    )
    estudos.salvar_rascunho(rascunho)

    from newport_app.models.cotacao_pdf import DocumentoCotacaoPDF, ExtracaoCotacaoCandidata

    extracao = ExtracaoCotacaoCandidata(
        id="ext-remover",
        estudo_id=estudo_id,
        versao=1,
        documento=DocumentoCotacaoPDF(
            id="doc-1",
            nome_arquivo="t.pdf",
            hash_sha256="h",
        ),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
    )
    extracoes.salvar(extracao)

    res = svc.remover_extracao(estudo_id, "ext-remover")
    assert res.removido
    assert res.planos_removidos == 1

    depois = estudos.obter_rascunho(estudo_id)
    assert depois is not None
    assert {op.id for op in depois.opcoes_proposta} == {"op-manter"}
    assert len(depois.cenarios[0].atribuicoes) == 1
    assert depois.cenarios[0].atribuicoes[0].opcao_plano_id == "op-manter"
    assert not depois.documentos_cotacao
