"""Reajuste para exibição — derivado de vigente/reajustado já no payload.

Não entra no ComparativoResponse hasheado. Uma função, matriz e HTML.
"""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    ComparativoComExibicao,
    ComparativoResponse,
    PlanoAtualComExibicao,
    PlanoAtualComparativo,
)
from newport_motor.money import round_half_up_from_numerator


def bps_variacao(base_centavos: int, novo_centavos: int) -> int | None:
    """Mesma fórmula de diff_bps, com half-up simétrico (não bankers)."""
    if base_centavos == 0:
        return None
    numerador = (novo_centavos - base_centavos) * 10_000
    if base_centavos > 0:
        return round_half_up_from_numerator(numerador, base_centavos)
    return -round_half_up_from_numerator(-numerador, -base_centavos)


def formatar_rotulo_reajuste_bps(bps: int) -> str:
    """0 → «0%»; positivo → «+N%»; negativo → «-N%»."""
    if bps == 0:
        return "0%"
    sinal = "+" if bps > 0 else "-"
    abs_bps = abs(bps)
    inteiro = abs_bps // 100
    dec = abs_bps % 100
    if dec == 0:
        return f"{sinal}{inteiro}%"
    return f"{sinal}{inteiro},{dec:02d}%"


def rotulo_reajuste_exibicao(
    *,
    vigente_centavos: int | None,
    reajustado_centavos: int | None,
    reajuste_bps_informado: int | None,
) -> str | None:
    """Rótulo por plano. ``None`` informado → omite percentual (não afirme 0%)."""
    if reajuste_bps_informado is None:
        return None
    if vigente_centavos is None or reajustado_centavos is None:
        return formatar_rotulo_reajuste_bps(reajuste_bps_informado)
    bps = bps_variacao(vigente_centavos, reajustado_centavos)
    if bps is None:
        return formatar_rotulo_reajuste_bps(reajuste_bps_informado)
    return formatar_rotulo_reajuste_bps(bps)


def rotulo_reajuste_consolidado(
    *,
    vigente_centavos: int | None,
    reajustado_centavos: int | None,
    reajustes_informados: list[int | None],
) -> str | None:
    """Efetivo pela razão dos consolidados. Todos nulos → omite (zero por ausência)."""
    if not reajustes_informados or all(b is None for b in reajustes_informados):
        return None
    if vigente_centavos is None or reajustado_centavos is None:
        return None
    bps = bps_variacao(vigente_centavos, reajustado_centavos)
    if bps is None:
        return None
    return formatar_rotulo_reajuste_bps(bps)


def _soma_centavos(planos: list[PlanoAtualComparativo], campo: str) -> int | None:
    vals = [getattr(p, campo) for p in planos if getattr(p, campo) is not None]
    if not vals:
        return None
    return sum(vals)


def _bps_por_subgrupo(rascunho: RascunhoEstudo) -> dict[str, int | None]:
    return {sg.id: sg.reajuste_bps for sg in rascunho.subgrupos_atuais}


def rotulos_reajuste_planos(
    planos: list[PlanoAtualComparativo],
    rascunho: RascunhoEstudo,
) -> dict[str, str | None]:
    bps_map = _bps_por_subgrupo(rascunho)
    out: dict[str, str | None] = {}
    for p in planos:
        out[p.subgrupo_id] = rotulo_reajuste_exibicao(
            vigente_centavos=p.vigente_centavos,
            reajustado_centavos=p.reajustado_centavos,
            reajuste_bps_informado=bps_map.get(p.subgrupo_id),
        )
    return out


def rotulo_reajuste_consolidado_dos_planos(
    planos: list[PlanoAtualComparativo],
    rascunho: RascunhoEstudo,
) -> str | None:
    bps_map = _bps_por_subgrupo(rascunho)
    informados = [bps_map.get(p.subgrupo_id) for p in planos]
    return rotulo_reajuste_consolidado(
        vigente_centavos=_soma_centavos(planos, "vigente_centavos"),
        reajustado_centavos=_soma_centavos(planos, "reajustado_centavos"),
        reajustes_informados=informados,
    )


def anexar_exibicao_reajuste(
    comparativo: ComparativoResponse,
    rascunho: RascunhoEstudo,
) -> ComparativoComExibicao:
    """Cópia para a API de tela — campos de exibição fora do dump hasheado."""
    por_plano = rotulos_reajuste_planos(comparativo.planos_atuais, rascunho)
    consolidado = rotulo_reajuste_consolidado_dos_planos(
        comparativo.planos_atuais, rascunho
    )
    planos = [
        PlanoAtualComExibicao(
            **p.model_dump(),
            reajuste_percentual_exibicao=por_plano.get(p.subgrupo_id),
        )
        for p in comparativo.planos_atuais
    ]
    return ComparativoComExibicao(
        **{
            **comparativo.model_dump(),
            "planos_atuais": planos,
            "reajuste_consolidado_percentual_exibicao": consolidado,
        }
    )
