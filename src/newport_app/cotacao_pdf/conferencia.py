"""Normalização de opções para conferência humana."""

from __future__ import annotations

from newport_app.cotacao_pdf.parsers.base import novo_campo
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata


def _garantir_campo(
    op: OpcaoCotacaoCandidata,
    attr: str,
    rotulo: str,
    *,
    parser_versao: str | None,
    documento_hash: str | None,
) -> None:
    if getattr(op, attr) is not None:
        return
    setattr(
        op,
        attr,
        novo_campo(
            rotulo,
            estado="ausente",
            parser_versao=parser_versao,
            documento_hash=documento_hash,
        ),
    )


def normalizar_opcao(
    op: OpcaoCotacaoCandidata,
    *,
    parser_versao: str | None,
    documento_hash: str | None,
) -> None:
    for attr, rotulo in (
        ("operadora", "Operadora"),
        ("plano_nome", "Nome do plano"),
        ("tipo_fiscal", "Tipo fiscal"),
        ("acomodacao", "Acomodação"),
        ("modalidade", "Modalidade"),
        ("regime_copart", "Regime de coparticipação"),
        ("copart_percentual", "Percentual de coparticipação"),
        ("validade_oficial", "Validade"),
        ("premio_saude", "Prêmio saúde"),
        ("iof", "IOF"),
        ("total_recorrente", "Total mensal"),
        ("total_primeira_parcela", "Primeira parcela"),
        ("subtotal_impresso", "Subtotal do plano"),
        ("observacoes", "Observações"),
    ):
        _garantir_campo(op, attr, rotulo, parser_versao=parser_versao, documento_hash=documento_hash)


def normalizar_extracao(extracao: ExtracaoCotacaoCandidata) -> ExtracaoCotacaoCandidata:
    doc_hash = extracao.documento.hash_sha256
    parser = extracao.documento.parser_versao
    for op in extracao.opcoes:
        normalizar_opcao(op, parser_versao=parser, documento_hash=doc_hash)
    return extracao
