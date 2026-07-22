"""Normalização monetária com price_basis e IOF (DP-02, P3)."""

from __future__ import annotations

from newport_motor.money import apply_rate_bps, round_half_up_from_numerator
from newport_motor.types import (
    MoneyCents,
    PriceBasis,
    RateBasisPoints,
    RoundingStrategy,
    TipoFiscal,
)


def tipo_fiscal_aplica_iof(tipo_fiscal: TipoFiscal) -> bool:
    return tipo_fiscal == TipoFiscal.SEGURADORA


def basis_e_conhecido(basis: PriceBasis) -> bool:
    return basis != PriceBasis.DESCONHECIDO


def para_base_exclui_iof(
    valor_centavos: int,
    price_basis: PriceBasis,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> int:
    """Converte valor para base exclui_iof quando IOF se aplica."""
    if price_basis == PriceBasis.DESCONHECIDO:
        raise ValueError("price_basis desconhecido não pode entrar no cálculo")
    if not tipo_fiscal_aplica_iof(tipo_fiscal):
        return valor_centavos
    if price_basis == PriceBasis.EXCLUI_IOF:
        return valor_centavos
    denominador = 10_000 + int(iof_bps)
    return round_half_up_from_numerator(valor_centavos * 10_000, denominador)


def aplicar_iof_se_necessario(
    valor_centavos: int,
    price_basis: PriceBasis,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> MoneyCents:
    """Converte componente para valor recorrente final (com IOF quando cabível)."""
    if price_basis == PriceBasis.DESCONHECIDO:
        raise ValueError("price_basis desconhecido não pode entrar no cálculo")
    if not tipo_fiscal_aplica_iof(tipo_fiscal):
        return MoneyCents(valor_centavos)
    if price_basis == PriceBasis.INCLUI_IOF:
        return MoneyCents(valor_centavos)
    return MoneyCents(apply_rate_bps(valor_centavos, iof_bps))


def normalizar_vidas_para_recorrente(
    valores_basis: list[tuple[int, PriceBasis]],
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
    strategy: RoundingStrategy,
) -> list[MoneyCents]:
    """
    Normaliza lista de valores para recorrente conforme estratégia de arredondamento.
    inclui_iof nunca recebe IOF novamente; exclui_iof segue a política.
    """
    if not valores_basis:
        return []

    for _, basis in valores_basis:
        if not basis_e_conhecido(basis):
            raise ValueError("price_basis desconhecido não pode entrar no cálculo")

    if not tipo_fiscal_aplica_iof(tipo_fiscal):
        return [MoneyCents(v) for v, _ in valores_basis]

    if strategy == RoundingStrategy.POR_VIDA_ENTAO_SOMA:
        result: list[MoneyCents] = []
        for valor, basis in valores_basis:
            if basis == PriceBasis.INCLUI_IOF:
                result.append(MoneyCents(valor))
            else:
                result.append(MoneyCents(apply_rate_bps(valor, iof_bps)))
        return result

    if strategy == RoundingStrategy.NO_TOTAL:
        return [
            MoneyCents(para_base_exclui_iof(v, b, tipo_fiscal, iof_bps))
            for v, b in valores_basis
        ]

    bases_exclui = [
        para_base_exclui_iof(v, b, tipo_fiscal, iof_bps) for v, b in valores_basis
    ]

    if strategy == RoundingStrategy.SOMA_ENTAO_APLICA:
        total_exclui = sum(bases_exclui)
        total_com_iof = apply_rate_bps(total_exclui, iof_bps)
        if len(bases_exclui) == 1:
            return [MoneyCents(total_com_iof)]
        partes: list[MoneyCents] = []
        acumulado = 0
        for base in bases_exclui[:-1]:
            parte = round_half_up_from_numerator(total_com_iof * base, total_exclui)
            partes.append(MoneyCents(parte))
            acumulado += parte
        partes.append(MoneyCents(total_com_iof - acumulado))
        return partes

    raise ValueError(f"Estratégia de arredondamento não suportada: {strategy}")


def total_recorrente_de_bases_exclui(
    bases_exclui: list[int],
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
    strategy: RoundingStrategy,
) -> MoneyCents:
    """Calcula total recorrente agregado; NO_TOTAL aplica IOF uma vez no total."""
    if not bases_exclui:
        return MoneyCents(0)
    if not tipo_fiscal_aplica_iof(tipo_fiscal):
        return MoneyCents(sum(bases_exclui))
    if strategy == RoundingStrategy.NO_TOTAL:
        return MoneyCents(apply_rate_bps(sum(bases_exclui), iof_bps))
    vals = normalizar_vidas_para_recorrente(
        [(b, PriceBasis.EXCLUI_IOF) for b in bases_exclui],
        tipo_fiscal,
        iof_bps,
        strategy,
    )
    return MoneyCents(sum(int(v) for v in vals))


def componente_para_recorrente(
    centavos: int,
    price_basis: PriceBasis,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> MoneyCents:
    return aplicar_iof_se_necessario(centavos, price_basis, tipo_fiscal, iof_bps)


def recorrente_de_premio_e_iof(
    premio_centavos: int,
    premio_basis: PriceBasis,
    iof_centavos: int | None,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> int:
    """
    Calcula recorrente a partir de prêmio e IOF explícito (reconciliação B-02).

    - iof.centavos = valor absoluto da linha de IOF; nunca recebe IOF novamente.
    - premio inclui_iof = total com IOF; linha IOF é informativa.
    - premio exclui_iof + IOF explícito = premio + iof (sem apply_rate_bps no IOF).
    - premio exclui_iof sem IOF explícito = aplica IOF via policy no prêmio.
    """
    if premio_basis == PriceBasis.DESCONHECIDO:
        raise ValueError("price_basis desconhecido no prêmio")

    if not tipo_fiscal_aplica_iof(tipo_fiscal):
        return premio_centavos

    if premio_basis == PriceBasis.INCLUI_IOF:
        return premio_centavos

    # premio exclui_iof
    if iof_centavos is not None:
        return premio_centavos + iof_centavos
    return int(aplicar_iof_se_necessario(premio_centavos, premio_basis, tipo_fiscal, iof_bps))


def somar_componentes_recorrentes(
    premio_centavos: int | None,
    premio_basis: PriceBasis,
    iof_centavos: int | None,
    iof_basis: PriceBasis,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> int | None:
    """Prêmio + IOF explícito normalizados para base recorrente comparável."""
    if premio_centavos is None:
        return None
    if premio_basis == PriceBasis.DESCONHECIDO:
        return None
    if iof_centavos is not None and iof_basis == PriceBasis.DESCONHECIDO:
        return None
    return recorrente_de_premio_e_iof(
        premio_centavos, premio_basis, iof_centavos, tipo_fiscal, iof_bps
    )


def recorrente_para_primeira_parcela(
    total_recorrente_centavos: int,
    total_recorrente_basis: PriceBasis,
    custos_unicos_centavos: int,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> int:
    """
    Equivalente recorrente + custos únicos (custos nunca recebem IOF).

    primeira_parcela_esperada = recorrente_normalizado + custos_unicos
    """
    recorrente = int(
        componente_para_recorrente(
            total_recorrente_centavos, total_recorrente_basis, tipo_fiscal, iof_bps
        )
    )
    return recorrente + custos_unicos_centavos


def primeira_parcela_normalizada(
    primeira_parcela_centavos: int,
    primeira_parcela_basis: PriceBasis,
    custos_unicos_centavos: int,
    tipo_fiscal: TipoFiscal,
    iof_bps: RateBasisPoints,
) -> int:
    """
    Normaliza primeira parcela para comparar com recorrente + custos.

    Se exclui_iof: normaliza apenas a parte recorrente (total - custos) e soma custos.
    Se inclui_iof: valor já inclui IOF na parcela recorrente; custos somados à parte.
    """
    if primeira_parcela_basis == PriceBasis.DESCONHECIDO:
        raise ValueError("price_basis desconhecido na primeira parcela")

    if primeira_parcela_centavos < custos_unicos_centavos:
        raise ValueError(
            "primeira parcela menor que custos únicos; validação estrutural obrigatória"
        )

    parte_recorrente_bruta = primeira_parcela_centavos - custos_unicos_centavos
    recorrente_norm = int(
        componente_para_recorrente(
            parte_recorrente_bruta, primeira_parcela_basis, tipo_fiscal, iof_bps
        )
    )
    return recorrente_norm + custos_unicos_centavos
