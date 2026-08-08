"""Descarte explícito de cotação PDF com motivo obrigatório."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
    ValorExtraido,
)
from newport_app.models.draft import (
    DocumentoCotacaoRascunho,
    OpcaoPropostaRascunho,
    RegimeCopartRascunho,
)
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.extracao_cotacao import (
    CotacaoDescartadaError,
    ExtracaoCotacaoService,
    MotivoDescarteObrigatorioError,
)
from newport_app.siscor_mapper.apply import rascunho_vazio


def _svc(tmp_path, monkeypatch):
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
    return ExtracaoCotacaoService(estudos, extracoes), estudos, extracoes


def _extracao(
    *,
    extracao_id: str,
    estudo_id: str,
    operadora: str,
    numero: str,
    selecionada: bool = False,
) -> ExtracaoCotacaoCandidata:
    return ExtracaoCotacaoCandidata(
        id=extracao_id,
        estudo_id=estudo_id,
        versao=1,
        documento=DocumentoCotacaoPDF(
            id=f"doc-{extracao_id}",
            nome_arquivo=f"{numero}.pdf",
            hash_sha256=f"h-{extracao_id}",
            operadora_detectada=operadora,
        ),
        estado="extraido",
        numero_cotacao=ValorExtraido(
            id=f"num-{extracao_id}",
            rotulo="Número da cotação",
            texto=numero,
        ),
        opcoes=[
            OpcaoCotacaoCandidata(
                id=f"op-{extracao_id}-1",
                selecionada_para_comparativo=selecionada,
            ),
            OpcaoCotacaoCandidata(
                id=f"op-{extracao_id}-2",
                selecionada_para_comparativo=False,
            ),
        ],
        criado_em=datetime.now(timezone.utc),
    )


def test_descarte_sem_motivo_recusado(tmp_path, monkeypatch):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    estudo_id = "est-desc-1"
    rascunho = rascunho_vazio(estudo_id, "Teste")
    estudos.salvar_rascunho(rascunho)
    extracoes.salvar(
        _extracao(extracao_id="ext-a", estudo_id=estudo_id, operadora="Porto", numero="1")
    )

    with pytest.raises(MotivoDescarteObrigatorioError):
        svc.descartar_extracao(estudo_id, "ext-a", motivo="   ")


def test_descarte_com_motivo_persiste_e_remove_do_comparativo(tmp_path, monkeypatch):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    estudo_id = "est-desc-2"
    rascunho = rascunho_vazio(estudo_id, "Teste")
    rascunho.regimes_copart.append(RegimeCopartRascunho(id="regime-sem", tipo="sem"))
    rascunho.documentos_cotacao.append(
        DocumentoCotacaoRascunho(id="doc-ext-sa", operadora="SulAmérica", hash="h-ext-sa")
    )
    rascunho.opcoes_proposta.append(
        OpcaoPropostaRascunho(
            id="op-sa",
            operadora="SulAmérica",
            plano_nome="Plano A",
            regime_copart_id="regime-sem",
            tipo_fiscal="seguradora",
            extracao_id="ext-sa",
            documento_cotacao_id="doc-ext-sa",
        )
    )
    estudos.salvar_rascunho(rascunho)
    extracoes.salvar(
        _extracao(
            extracao_id="ext-sa",
            estudo_id=estudo_id,
            operadora="SulAmérica",
            numero="7969363-1",
            selecionada=True,
        )
    )

    res = svc.descartar_extracao(estudo_id, "ext-sa", motivo="fora do perfil")
    assert res.descartada is True
    assert res.motivo == "fora do perfil"
    assert res.planos_removidos == 1

    salva = extracoes.obter_por_id("ext-sa")
    assert salva is not None
    assert salva.descartada is True
    assert salva.motivo_descarte == "fora do perfil"
    assert all(not o.selecionada_para_comparativo for o in salva.opcoes)

    depois = estudos.obter_rascunho(estudo_id)
    assert depois is not None
    assert depois.opcoes_proposta == []


def test_aplicar_cotacao_descartada_bloqueado(tmp_path, monkeypatch):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    estudo_id = "est-desc-3"
    estudos.salvar_rascunho(rascunho_vazio(estudo_id, "Teste"))
    extracoes.salvar(
        _extracao(
            extracao_id="ext-b",
            estudo_id=estudo_id,
            operadora="Porto",
            numero="P1",
            selecionada=True,
        )
    )
    svc.descartar_extracao(estudo_id, "ext-b", motivo="vencida")

    with pytest.raises(CotacaoDescartadaError):
        svc.aplicar_ao_rascunho("ext-b")


def test_reverter_descarte_permite_nova_selecao(tmp_path, monkeypatch):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    estudo_id = "est-desc-4"
    estudos.salvar_rascunho(rascunho_vazio(estudo_id, "Teste"))
    extracoes.salvar(
        _extracao(extracao_id="ext-c", estudo_id=estudo_id, operadora="Porto", numero="P2")
    )
    svc.descartar_extracao(estudo_id, "ext-c", motivo="não competitiva")
    revertida = svc.reverter_descarte_extracao(estudo_id, "ext-c")
    assert revertida.descartada is False
    assert revertida.motivo_descarte is None
