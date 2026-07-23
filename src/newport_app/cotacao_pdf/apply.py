"""Aplicação de extrações confirmadas ao RascunhoEstudo."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    DocumentoCotacaoRascunho,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RascunhoEstudo,
    RegimeCopartRascunho,
    TabelaFaixaRascunho,
)


def _prov_extraida(campo, documento_id: str, parser_versao: str) -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.EXTRAIDO,
        documento_id=documento_id,
        extrator_versao=parser_versao or "cotacao-pdf",
        confirmado=bool(campo and campo.confirmado),
    )


def _comp(campo, documento_id: str, parser_versao: str) -> ComponenteFinanceiroRascunho | None:
    if campo is None or campo.centavos is None:
        return None
    return ComponenteFinanceiroRascunho(
        centavos=campo.centavos,
        price_basis=campo.price_basis or PriceBasisRascunho.DESCONHECIDO,
        proveniencia=_prov_extraida(campo, documento_id, parser_versao),
    )


def _regime_id(texto: str | None) -> str | None:
    if not texto:
        return None
    mapa = {
        "sem": "regime-sem",
        "parcial": "regime-parcial",
        "percentual": "regime-percentual",
        "customizada": "regime-customizada",
    }
    return mapa.get(texto.lower(), f"regime-{texto.lower()}")


def _ensure_regime(rascunho: RascunhoEstudo, regime_id: str | None) -> None:
    if not regime_id:
        return
    tipo = regime_id.replace("regime-", "")
    if not any(r.id == regime_id for r in rascunho.regimes_copart):
        rascunho.regimes_copart.append(RegimeCopartRascunho(id=regime_id, tipo=tipo))  # type: ignore[arg-type]


def opcao_candidata_para_rascunho(
    op: OpcaoCotacaoCandidata,
    *,
    documento_id: str,
    parser_versao: str,
) -> OpcaoPropostaRascunho | None:
    if op.excluida:
        return None
    if not op.plano_nome or not op.plano_nome.texto:
        return None
    regime_txt = op.regime_copart.texto if op.regime_copart else None
    regime_id = _regime_id(regime_txt)
    tabela: list[TabelaFaixaRascunho] = []
    for fx in op.tabela:
        if fx.valor.centavos is None:
            continue
        if not fx.valor.confirmado:
            continue
        tabela.append(
            TabelaFaixaRascunho(
                faixa=fx.faixa,
                valor_centavos=fx.valor.centavos,
                quantidade_cotada=fx.quantidade.inteiro if fx.quantidade.confirmado else None,
                price_basis=fx.valor.price_basis or PriceBasisRascunho.DESCONHECIDO,
                proveniencia=_prov_extraida(fx.valor, documento_id, parser_versao),
            )
        )
    tipo_fiscal = op.tipo_fiscal.texto if op.tipo_fiscal and op.tipo_fiscal.confirmado else None
    return OpcaoPropostaRascunho(
        id=str(uuid.uuid4()),
        operadora=op.operadora.texto if op.operadora else "",
        plano_nome=op.plano_nome.texto or "",
        regime_copart_id=regime_id or "regime-sem",
        tipo_fiscal=tipo_fiscal or "seguradora",  # type: ignore[arg-type]
        acomodacao=op.acomodacao.texto if op.acomodacao and op.acomodacao.confirmado else None,
        modalidade=None,
        tabela=tabela,
        premio_saude=_comp(op.premio_saude, documento_id, parser_versao),
        iof=_comp(op.iof, documento_id, parser_versao),
        total_recorrente=_comp(op.total_recorrente, documento_id, parser_versao),
        total_primeira_parcela=_comp(op.total_primeira_parcela, documento_id, parser_versao),
        subtotal_impresso=_comp(op.subtotal_impresso, documento_id, parser_versao),
        documento_cotacao_id=documento_id,
        validade_oficial=(
            op.validade_oficial.data if op.validade_oficial and op.validade_oficial.confirmado else None
        ),
        observacoes=op.observacoes.texto if op.observacoes and op.observacoes.confirmado else None,
    )


def aplicar_extracao_confirmada(
    rascunho: RascunhoEstudo,
    extracao: ExtracaoCotacaoCandidata,
) -> RascunhoEstudo:
    doc = extracao.documento
    if not any(d.id == doc.id for d in rascunho.documentos_cotacao):
        rascunho.documentos_cotacao.append(
            DocumentoCotacaoRascunho(
                id=doc.id,
                operadora=doc.operadora_detectada or "Desconhecida",
                hash=doc.hash_sha256,
                parser_versao=doc.parser_versao or "cotacao-pdf",
                estado_extracao="extraido",
                validade_oficial=(
                    extracao.validade_oficial.data
                    if extracao.validade_oficial and extracao.validade_oficial.confirmado
                    else None
                ),
                data_emissao=(
                    extracao.data_emissao.data
                    if extracao.data_emissao and extracao.data_emissao.confirmado
                    else None
                ),
            )
        )
    parser_versao = doc.parser_versao or "cotacao-pdf"
    for op_c in extracao.opcoes:
        if op_c.excluida:
            continue
        regime_id = _regime_id(op_c.regime_copart.texto if op_c.regime_copart else None)
        _ensure_regime(rascunho, regime_id)
        opcao = opcao_candidata_para_rascunho(
            op_c,
            documento_id=doc.id,
            parser_versao=parser_versao,
        )
        if opcao is not None and opcao.tabela:
            rascunho.opcoes_proposta.append(opcao)
    return rascunho
