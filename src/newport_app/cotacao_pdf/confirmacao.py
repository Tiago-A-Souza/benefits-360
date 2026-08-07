"""Confirmação implícita de campos extraídos (seleção ou aplicação ao comparativo)."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata, ValorExtraido


def _campo_preenchido(campo: ValorExtraido) -> bool:
    return any(v is not None for v in (campo.texto, campo.centavos, campo.data, campo.inteiro))


def _iter_campos_opcao(op: OpcaoCotacaoCandidata):
    for attr in (
        op.operadora,
        op.plano_nome,
        op.tipo_fiscal,
        op.acomodacao,
        op.modalidade,
        op.regime_copart,
        op.copart_percentual,
        op.premio_saude,
        op.iof,
        op.total_recorrente,
        op.total_primeira_parcela,
        op.subtotal_impresso,
        op.validade_oficial,
        op.observacoes,
    ):
        if attr is not None:
            yield attr
    for fx in op.tabela:
        yield fx.valor
        yield fx.quantidade
    for custo in op.custos_unicos:
        yield custo


def _confirmar_campo(campo: ValorExtraido, *, confirmado_por: str, agora: datetime) -> bool:
    if not _campo_preenchido(campo):
        return False
    if campo.confirmado:
        return False
    campo.confirmado = True
    campo.confirmado_por = confirmado_por
    campo.confirmado_em = agora
    return True


def _aplicar_defaults_opcao(op: OpcaoCotacaoCandidata) -> None:
    if op.tipo_fiscal is not None and not op.tipo_fiscal.texto:
        op.tipo_fiscal.texto = "seguradora"
    if op.regime_copart is not None and not op.regime_copart.texto:
        op.regime_copart.texto = "sem"


def confirmar_opcao_implicita(
    op: OpcaoCotacaoCandidata,
    *,
    confirmado_por: str = "analista-local",
) -> int:
    """Aceita valores extraídos preenchidos — seleção ou aplicação implica revisão ok."""
    if op.excluida:
        return 0
    _aplicar_defaults_opcao(op)
    agora = datetime.now(timezone.utc)
    confirmados = 0
    for campo in _iter_campos_opcao(op):
        if _confirmar_campo(campo, confirmado_por=confirmado_por, agora=agora):
            confirmados += 1
    reconciliar_opcao(op)
    return confirmados


def _validade_referencia_extracao(
    extracao: ExtracaoCotacaoCandidata,
    op: OpcaoCotacaoCandidata,
):
    if extracao.validade_oficial and extracao.validade_oficial.data:
        return extracao.validade_oficial.data
    if op.validade_oficial and op.validade_oficial.data:
        return op.validade_oficial.data
    for candidata in extracao.opcoes:
        if candidata.validade_oficial and candidata.validade_oficial.data:
            return candidata.validade_oficial.data
    return None


def _propagar_validade_documento(
    extracao: ExtracaoCotacaoCandidata,
    op: OpcaoCotacaoCandidata,
) -> None:
    validade = _validade_referencia_extracao(extracao, op)
    if not validade:
        return
    if extracao.validade_oficial is not None and not extracao.validade_oficial.data:
        extracao.validade_oficial.data = validade
    if op.validade_oficial is not None and not op.validade_oficial.data:
        op.validade_oficial.data = validade


def confirmar_extracao_selecionadas(
    extracao: ExtracaoCotacaoCandidata,
    *,
    confirmado_por: str = "analista-local",
) -> int:
    total = 0
    agora = datetime.now(timezone.utc)
    if extracao.validade_oficial and _confirmar_campo(
        extracao.validade_oficial, confirmado_por=confirmado_por, agora=agora
    ):
        total += 1
    if extracao.data_emissao and _confirmar_campo(
        extracao.data_emissao, confirmado_por=confirmado_por, agora=agora
    ):
        total += 1
    for op in extracao.opcoes:
        if op.excluida or not op.selecionada_para_comparativo:
            continue
        _propagar_validade_documento(extracao, op)
        total += confirmar_opcao_implicita(op, confirmado_por=confirmado_por)
    return total
