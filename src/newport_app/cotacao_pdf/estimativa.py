"""Estimativa mensal de proposta alinhada ao motor (IOF / price_basis)."""

from __future__ import annotations

from newport_app.draft_compiler.mapper import mapear_price_basis
from newport_app.models.compilation import ErroCompilacao
from newport_app.models.cotacao_pdf import OpcaoCotacaoCandidata
from newport_app.models.draft import OpcaoPropostaRascunho, PriceBasisRascunho, TabelaFaixaRascunho
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO, default_registry
from newport_motor.finance import normalizar_vidas_para_recorrente
from newport_motor.types import PriceBasis, RateBasisPoints, RoundingStrategy, TipoFiscal


def _tipo_fiscal_texto(texto: str | None) -> str:
    if texto and texto.strip().lower() == "operadora":
        return "operadora"
    return "seguradora"


def _tipo_fiscal_motor(texto: str | None) -> TipoFiscal:
    return (
        TipoFiscal.OPERADORA
        if _tipo_fiscal_texto(texto) == "operadora"
        else TipoFiscal.SEGURADORA
    )


def _iof_bps_padrao() -> RateBasisPoints:
    policy = default_registry.resolve(POLICY_SET_VERSAO_PADRAO)
    assert policy is not None
    return policy.iof_bps


def _basis_motor(
    basis_rasc: PriceBasisRascunho | None,
    tipo_fiscal: str,
    caminho: str,
) -> PriceBasis | None:
    basis = mapear_price_basis(
        basis_rasc or PriceBasisRascunho.EXCLUI_IOF,
        tipo_fiscal,
        caminho,
    )
    if isinstance(basis, ErroCompilacao):
        return None
    return basis


def estimar_total_tabela_rascunho(
    tabela: list[TabelaFaixaRascunho],
    quantidades: dict[int, int],
    *,
    tipo_fiscal: str | None,
    iof_bps: RateBasisPoints | None = None,
) -> int | None:
    """Soma normalizada (mesma regra por-vida do motor) para opção já no rascunho."""
    tf_txt = _tipo_fiscal_texto(tipo_fiscal)
    tf = _tipo_fiscal_motor(tipo_fiscal)
    iof = iof_bps or _iof_bps_padrao()
    por_faixa = {fx.faixa: fx for fx in tabela}
    valores_basis: list[tuple[int, PriceBasis]] = []

    for faixa, qtd in quantidades.items():
        if qtd <= 0:
            continue
        fx = por_faixa.get(int(faixa))
        if fx is None:
            continue
        basis = _basis_motor(fx.price_basis, tf_txt, f"tabela/{faixa}/valor")
        if basis is None:
            continue
        for _ in range(qtd):
            valores_basis.append((fx.valor_centavos, basis))

    if not valores_basis:
        return None

    normalizados = normalizar_vidas_para_recorrente(
        valores_basis,
        tf,
        iof,
        RoundingStrategy.POR_VIDA_ENTAO_SOMA,
    )
    return sum(int(v) for v in normalizados)


def estimar_opcao_candidata(
    opcao: OpcaoCotacaoCandidata,
    quantidades: dict[int, int],
    *,
    iof_bps: RateBasisPoints | None = None,
) -> int | None:
    """Estimativa mensal para linha da etapa 3 (extração PDF)."""
    tf_txt = _tipo_fiscal_texto(opcao.tipo_fiscal.texto if opcao.tipo_fiscal else None)
    tf = _tipo_fiscal_motor(opcao.tipo_fiscal.texto if opcao.tipo_fiscal else None)
    iof = iof_bps or _iof_bps_padrao()
    por_faixa = {fx.faixa: fx for fx in opcao.tabela}
    valores_basis: list[tuple[int, PriceBasis]] = []

    for faixa, qtd in quantidades.items():
        if qtd <= 0:
            continue
        fx = por_faixa.get(int(faixa))
        if fx is None or fx.valor.centavos is None:
            continue
        basis = _basis_motor(
            fx.valor.price_basis,
            tf_txt,
            f"opcao/{opcao.id}/faixa/{faixa}/valor",
        )
        if basis is None:
            continue
        for _ in range(qtd):
            valores_basis.append((fx.valor.centavos, basis))

    if not valores_basis:
        return None

    normalizados = normalizar_vidas_para_recorrente(
        valores_basis,
        tf,
        iof,
        RoundingStrategy.POR_VIDA_ENTAO_SOMA,
    )
    return sum(int(v) for v in normalizados)


def estimar_opcao_rascunho(
    opcao: OpcaoPropostaRascunho,
    quantidades: dict[int, int],
    *,
    iof_bps: RateBasisPoints | None = None,
) -> int | None:
    return estimar_total_tabela_rascunho(
        opcao.tabela,
        quantidades,
        tipo_fiscal=opcao.tipo_fiscal,
        iof_bps=iof_bps,
    )
