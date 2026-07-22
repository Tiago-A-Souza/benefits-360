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
    # inclui_iof: remove IOF embutido
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

    if strategy == RoundingStrategy.NO_TOTAL:
        # Por vida: normaliza basis para exclui_iof sem aplicar IOF (IOF só no total)
        return [
            MoneyCents(para_base_exclui_iof(v, b, tipo_fiscal, iof_bps))
            for v, b in valores_basis
        ]

    bases_exclui = [
        para_base_exclui_iof(v, b, tipo_fiscal, iof_bps) for v, b in valores_basis
    ]

    if strategy == RoundingStrategy.POR_VIDA_ENTAO_SOMA:
        return [MoneyCents(apply_rate_bps(b, iof_bps)) for b in bases_exclui]

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
    premio_rec = int(
        componente_para_recorrente(premio_centavos, premio_basis, tipo_fiscal, iof_bps)
    )
    if iof_centavos is None:
        return premio_rec
    if iof_basis == PriceBasis.DESCONHECIDO:
        return None
    if iof_basis == PriceBasis.INCLUI_IOF:
        iof_add = iof_centavos
    else:
        iof_add = int(componente_para_recorrente(iof_centavos, iof_basis, tipo_fiscal, iof_bps))
    return premio_rec + iof_add
