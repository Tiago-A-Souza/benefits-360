"""Resolução explícita de precedencia_atual_vida — sem omissão no motor."""

from __future__ import annotations

from datetime import date
from typing import Literal

from newport_app.models.draft import (
    CampoConfirmavelPrecedencia,
    OrigemValorRascunho,
    RascunhoEstudo,
)
from newport_motor.faixa import faixa_de_idade, idade_completa_em

PrecedenciaValor = Literal["valor_fatura", "tabela_atual"]


def _data_referencia(rascunho: RascunhoEstudo) -> date | None:
    return rascunho.escolhas.data_referencia_idade


def precedencia_ambigua(rascunho: RascunhoEstudo) -> bool:
    """True quando tabela e fatura coexistem na mesma faixa de alguma vida (DP-02 / B-07)."""
    if rascunho.formato != "renovacao":
        return False
    ref = _data_referencia(rascunho)
    if ref is None:
        return False
    subgrupos = {sg.id: sg for sg in rascunho.subgrupos_atuais}
    for vida in rascunho.vidas_incluidas():
        if not vida.subgrupo_atual_id or vida.valor_fatura is None:
            continue
        if vida.valor_fatura.centavos is None:
            continue
        subgrupo = subgrupos.get(vida.subgrupo_atual_id)
        if subgrupo is None or not subgrupo.tabela_atual:
            continue
        if vida.nascimento > ref:
            continue
        idade = idade_completa_em(vida.nascimento, ref)
        faixa = faixa_de_idade(idade)
        if any(t.faixa == faixa for t in subgrupo.tabela_atual):
            return True
    return False


def _tem_fatura(rascunho: RascunhoEstudo) -> bool:
    return any(
        v.valor_fatura is not None and v.valor_fatura.centavos is not None
        for v in rascunho.vidas_incluidas()
    )


def _tem_tabela(rascunho: RascunhoEstudo) -> bool:
    return any(bool(sg.tabela_atual) for sg in rascunho.subgrupos_atuais)


def resolver_precedencia_unica(rascunho: RascunhoEstudo) -> PrecedenciaValor | None:
    """Fonte única quando não há ambiguidade. None se ambíguo ou sem fonte."""
    if rascunho.formato != "renovacao":
        return None
    if precedencia_ambigua(rascunho):
        return None
    tem_fatura = _tem_fatura(rascunho)
    tem_tabela = _tem_tabela(rascunho)
    if tem_fatura:
        return "valor_fatura"
    if tem_tabela:
        return "tabela_atual"
    return None


def aplicar_precedencia_explicita(rascunho: RascunhoEstudo) -> PrecedenciaValor | None:
    """Grava valor explícito e confirmado quando a fonte é única e ainda não há escolha.

    Não sobrescreve valor já confirmado (estudos legados). Não escolhe se ambíguo.
    """
    if rascunho.formato != "renovacao":
        return None
    if precedencia_ambigua(rascunho):
        return None
    resolvido = resolver_precedencia_unica(rascunho)
    if resolvido is None:
        return None
    atual = rascunho.escolhas.precedencia_atual_vida
    if atual.valor is not None and atual.confirmado:
        return atual.valor
    rascunho.escolhas.precedencia_atual_vida = CampoConfirmavelPrecedencia(
        valor=resolvido,
        confirmado=True,
    )
    return resolvido


def descricao_origem_valores(rascunho: RascunhoEstudo) -> str:
    """Texto de transparência para a etapa 2 — reflete a fonte em uso, não um rótulo fixo."""
    if rascunho.formato != "renovacao":
        return "Seguro novo — sem contrato vigente para comparar."
    if precedencia_ambigua(rascunho):
        return (
            "Tabela tarifária e valor de fatura coexistem na mesma faixa de ao menos "
            "um beneficiário. Escolha qual fonte prevalece."
        )
    resolvido = resolver_precedencia_unica(rascunho)
    if resolvido == "valor_fatura":
        origens = {
            (v.valor_fatura.proveniencia.origem if v.valor_fatura and v.valor_fatura.proveniencia else None)
            for v in rascunho.vidas_incluidas()
            if v.valor_fatura is not None and v.valor_fatura.centavos is not None
        }
        origens.discard(None)
        if OrigemValorRascunho.EXTRAIDO in origens:
            return "Origem em uso: valores de fatura importados do SISCOR (coluna VALOR)."
        if OrigemValorRascunho.MANUAL in origens and len(origens) == 1:
            return "Origem em uso: valores de fatura informados manualmente por beneficiário."
        return "Origem em uso: valores de fatura por beneficiário."
    if resolvido == "tabela_atual":
        return "Origem em uso: tabela tarifária do plano atual."
    return "Nenhuma fonte de valor atual encontrada nesta base (sem fatura e sem tabela)."
