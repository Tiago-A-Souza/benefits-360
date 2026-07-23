"""Reconciliação financeira de opções extraídas."""

from __future__ import annotations

from newport_app.models.cotacao_pdf import (
    DivergenciaReconciliacao,
    OpcaoCotacaoCandidata,
    ReconciliacaoOpcao,
)
from newport_app.models.draft import PriceBasisRascunho


def _centavos(campo) -> int | None:
    return campo.centavos if campo is not None else None


def _inteiro(campo) -> int:
    if campo is None or campo.inteiro is None:
        return 0
    return campo.inteiro


def reconciliar_opcao(opcao: OpcaoCotacaoCandidata) -> ReconciliacaoOpcao:
    divergencias: list[DivergenciaReconciliacao] = []
    subtotal_calc = 0
    tem_faixa = False
    for faixa in opcao.tabela:
        qtd = _inteiro(faixa.quantidade)
        valor = faixa.valor.centavos
        if qtd and valor is not None:
            tem_faixa = True
            subtotal_calc += qtd * valor
        elif valor is not None and qtd == 0:
            continue

    subtotal_inf = _centavos(opcao.subtotal_impresso) or _centavos(opcao.premio_saude)
    premio = _centavos(opcao.premio_saude)
    iof = _centavos(opcao.iof)
    total_inf = _centavos(opcao.total_recorrente)
    primeira_inf = _centavos(opcao.total_primeira_parcela)
    custos_unicos = sum(_centavos(c) or 0 for c in opcao.custos_unicos)

    total_calc = subtotal_calc
    if premio is not None:
        total_calc = premio
        if iof is not None:
            total_calc = premio + iof

    if tem_faixa and subtotal_inf is not None and subtotal_inf != subtotal_calc:
        divergencias.append(
            DivergenciaReconciliacao(
                codigo="REC-SUB",
                descricao="O subtotal calculado pelas faixas não coincide com o subtotal informado.",
                esperado_centavos=subtotal_calc,
                informado_centavos=subtotal_inf,
            )
        )
    if premio is not None and tem_faixa and subtotal_calc and premio != subtotal_calc:
        divergencias.append(
            DivergenciaReconciliacao(
                codigo="REC-PREMIO",
                descricao="O prêmio informado difere da soma quantidade × valor por faixa.",
                esperado_centavos=subtotal_calc,
                informado_centavos=premio,
            )
        )
    if total_inf is not None and premio is not None and iof is not None:
        esperado_total = premio + iof
        if total_inf != esperado_total:
            divergencias.append(
                DivergenciaReconciliacao(
                    codigo="REC-IOF",
                    descricao="Prêmio + IOF não coincide com o total recorrente informado.",
                    esperado_centavos=esperado_total,
                    informado_centavos=total_inf,
                )
            )
    if primeira_inf is not None and total_inf is not None:
        esperado_1a = total_inf + custos_unicos
        if primeira_inf != esperado_1a:
            divergencias.append(
                DivergenciaReconciliacao(
                    codigo="REC-1PARCELA",
                    descricao="A primeira parcela difere do total recorrente mais custos únicos.",
                    esperado_centavos=esperado_1a,
                    informado_centavos=primeira_inf,
                )
            )

    rec = ReconciliacaoOpcao(
        subtotal_calculado_centavos=subtotal_calc if tem_faixa else None,
        subtotal_informado_centavos=subtotal_inf,
        total_recorrente_calculado_centavos=total_calc if tem_faixa or premio else None,
        total_recorrente_informado_centavos=total_inf,
        primeira_parcela_calculada_centavos=(
            (total_inf or total_calc) + custos_unicos
            if (total_inf or total_calc) is not None
            else None
        ),
        primeira_parcela_informada_centavos=primeira_inf,
        divergencias=divergencias,
        ok=not divergencias,
    )
    opcao.reconciliacao = rec
    return rec
