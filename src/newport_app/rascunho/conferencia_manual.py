"""Conferência de totais digitados na entrada manual — wrapper da reconciliação do motor.

Não altera o motor: só monta DadosReconciliacaoOpcao, chama reconciliar_opcao_cenario
e traduz o diff para os limiares de UX do piloto (≤5c ok; ≤100c aviso; >100c bloqueio).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from newport_app.models.draft import OpcaoPropostaRascunho, PriceBasisRascunho
from newport_motor.finance import aplicar_iof_se_necessario, componente_para_recorrente
from newport_motor.models import OpcaoPlano, TabelaPrecoFaixa
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.reconciliation import DadosReconciliacaoOpcao, reconciliar_opcao_cenario
from newport_motor.types import (
    OrigemValor,
    PriceBasis,
    TipoFiscal,
)

LIMIAR_OK_CENTAVOS = 5  # R$ 0,05 — alinhado a TolerancePolicy.total_centavos
LIMIAR_AVISO_CENTAVOS = 100  # R$ 1,00


class SeveridadeConferenciaManual(str, Enum):
    OK = "ok"
    AVISO = "aviso"
    BLOQUEIO = "bloqueio"


@dataclass(frozen=True)
class ResultadoConferenciaManual:
    severidade: SeveridadeConferenciaManual
    mensagem: str
    total_calculado_centavos: int | None = None
    total_informado_centavos: int | None = None
    diff_centavos: int | None = None
    totais_nao_constam: bool = False


def _basis_motor(pb: PriceBasisRascunho | str | None, tipo_fiscal: TipoFiscal) -> PriceBasis:
    raw = pb.value if isinstance(pb, PriceBasisRascunho) else pb
    if raw in (None, "", "desconhecido"):
        return PriceBasis.DESCONHECIDO
    if raw == "nao_aplica":
        return PriceBasis.NAO_APLICA if tipo_fiscal == TipoFiscal.OPERADORA else PriceBasis.EXCLUI_IOF
    return PriceBasis(raw)


def _comp_motor(comp, tipo_fiscal: TipoFiscal) -> ComponenteFinanceiro | None:
    if comp is None or comp.centavos is None:
        return None
    return ComponenteFinanceiro(
        centavos=comp.centavos,
        price_basis=_basis_motor(comp.price_basis, tipo_fiscal),
        proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL, extrator_versao="manual"),
    )


def subtotal_faixas_puro_centavos(opcao: OpcaoPropostaRascunho) -> int:
    total = 0
    for fx in opcao.tabela:
        if fx.valor_centavos is None:
            continue
        qtd = 0 if fx.quantidade_cotada is None else int(fx.quantidade_cotada)
        total += qtd * int(fx.valor_centavos)
    return total


def total_recorrente_calculado_centavos(
    opcao: OpcaoPropostaRascunho,
    *,
    iof_bps: int = 238,
) -> int | None:
    """Soma faixas e aplica IOF conforme tipo_fiscal + price_basis dominante das faixas."""
    if not opcao.tipo_fiscal:
        return None
    tf = TipoFiscal(opcao.tipo_fiscal)
    puro = 0
    # Normaliza faixa a faixa (estratégia por_vida_entao_soma aproximada na agregação
    # de quantidades cotadas — suficiente para conferência de entrada).
    for fx in opcao.tabela:
        if fx.valor_centavos is None:
            continue
        qtd = 0 if fx.quantidade_cotada is None else int(fx.quantidade_cotada)
        if qtd <= 0:
            continue
        basis = _basis_motor(fx.price_basis, tf)
        if basis == PriceBasis.DESCONHECIDO:
            return None
        unit_rec = int(aplicar_iof_se_necessario(fx.valor_centavos, basis, tf, iof_bps))
        puro += unit_rec * qtd
    return puro


def _opcao_plano_para_reconciliar(opcao: OpcaoPropostaRascunho) -> OpcaoPlano | None:
    if not opcao.tipo_fiscal:
        return None
    tf = TipoFiscal(opcao.tipo_fiscal)
    tabela: list[TabelaPrecoFaixa] = []
    for fx in opcao.tabela:
        if fx.valor_centavos is None:
            continue
        basis = _basis_motor(fx.price_basis, tf)
        if basis == PriceBasis.DESCONHECIDO:
            continue
        tabela.append(
            TabelaPrecoFaixa(
                faixa=fx.faixa,
                valor_centavos=fx.valor_centavos,
                quantidade_cotada=0 if fx.quantidade_cotada is None else fx.quantidade_cotada,
                price_basis=basis,
                proveniencia=ProvenienciaCampo(
                    origem=OrigemValor.MANUAL, extrator_versao="manual"
                ),
            )
        )
    return OpcaoPlano(
        id=opcao.id,
        operadora=opcao.operadora or "",
        plano_nome=opcao.plano_nome or "",
        regime_copart_id=opcao.regime_copart_id or "regime-sem",
        tipo_fiscal=tf,
        tabela=tabela,
        premio_saude=_comp_motor(opcao.premio_saude, tf),
        iof=_comp_motor(opcao.iof, tf),
        total_recorrente=_comp_motor(opcao.total_recorrente, tf),
        total_primeira_parcela=_comp_motor(opcao.total_primeira_parcela, tf),
        subtotal_impresso=_comp_motor(opcao.subtotal_impresso, tf),
        custos_unicos=[],
    )


def _fmt_reais(centavos: int) -> str:
    neg = centavos < 0
    c = abs(centavos)
    corpo = f"{c // 100}.{c % 100:02d}"
    # milhares
    reais, frac = corpo.split(".")
    reais_fmt = f"{int(reais):,}".replace(",", ".")
    s = f"R$ {reais_fmt},{frac}"
    return f"-{s}" if neg else s


def conferir_totais_opcao_manual(
    opcao: OpcaoPropostaRascunho,
    *,
    policy: EffectivePolicy | None = None,
) -> ResultadoConferenciaManual:
    """Conferência UX da entrada manual.

    - ``totais_impressos_nao_constam``: não bloqueia; devolve aviso visível.
    - Sem total informado: ok (nada a conferir).
    - Com total: compara com cálculo das faixas (+ IOF) via limiares do piloto,
      reutilizando ``reconciliar_opcao_cenario`` para a normalização B-02.
    """
    if getattr(opcao, "totais_impressos_nao_constam", False):
        return ResultadoConferenciaManual(
            severidade=SeveridadeConferenciaManual.AVISO,
            mensagem=(
                "Totais impressos marcados como «não constam no PDF». "
                "A conferência automática está desligada para esta cotação."
            ),
            totais_nao_constam=True,
        )

    informado = None
    if opcao.total_recorrente and opcao.total_recorrente.centavos is not None:
        informado = int(opcao.total_recorrente.centavos)
    elif opcao.subtotal_impresso and opcao.subtotal_impresso.centavos is not None:
        informado = int(opcao.subtotal_impresso.centavos)

    if informado is None:
        return ResultadoConferenciaManual(
            severidade=SeveridadeConferenciaManual.OK,
            mensagem="Nenhum total impresso informado para conferência.",
        )

    if not opcao.tipo_fiscal:
        return ResultadoConferenciaManual(
            severidade=SeveridadeConferenciaManual.AVISO,
            mensagem="Informe o tipo fiscal antes de conferir o total impresso.",
            total_informado_centavos=informado,
        )

    pol = policy or EffectivePolicy()
    calc = total_recorrente_calculado_centavos(opcao, iof_bps=int(pol.iof_bps))
    if calc is None:
        return ResultadoConferenciaManual(
            severidade=SeveridadeConferenciaManual.AVISO,
            mensagem=(
                "Não foi possível calcular o total pelas faixas — "
                "complete valores e base de IOF de cada faixa."
            ),
            total_informado_centavos=informado,
        )

    # Normaliza o impresso para recorrente (mesma função que o motor usa na B-02).
    tf = TipoFiscal(opcao.tipo_fiscal)
    comp_info = opcao.total_recorrente or opcao.subtotal_impresso
    assert comp_info is not None and comp_info.centavos is not None
    basis_info = _basis_motor(comp_info.price_basis, tf)
    if basis_info == PriceBasis.DESCONHECIDO:
        # Assume mesma base das faixas se o analista não declarou no total.
        bases_fx = {
            _basis_motor(fx.price_basis, tf)
            for fx in opcao.tabela
            if fx.valor_centavos is not None
        }
        bases_fx.discard(PriceBasis.DESCONHECIDO)
        basis_info = next(iter(bases_fx)) if len(bases_fx) == 1 else PriceBasis.EXCLUI_IOF
    informado_norm = int(
        componente_para_recorrente(informado, basis_info, tf, int(pol.iof_bps))
    )

    op_plano = _opcao_plano_para_reconciliar(opcao)
    if op_plano is not None and op_plano.total_recorrente is not None:
        # Garante basis conhecido no componente passado ao motor.
        if op_plano.total_recorrente.price_basis == PriceBasis.DESCONHECIDO:
            op_plano = op_plano.model_copy(
                update={
                    "total_recorrente": ComponenteFinanceiro(
                        centavos=op_plano.total_recorrente.centavos,
                        price_basis=basis_info,
                        proveniencia=op_plano.total_recorrente.proveniencia,
                    )
                }
            )
        reconciliar_opcao_cenario(
            DadosReconciliacaoOpcao(
                opcao_id=opcao.id,
                opcao=op_plano,
                vidas=[],
                subgrupos=[],
                total_calculado_centavos=calc,
            ),
            pol,
        )
        # Severidade do motor (bloqueia >5c) é mais estrita que o aviso do piloto;
        # a UX da entrada manual usa os limiares abaixo.

    diff = abs(calc - informado_norm)
    if diff <= LIMIAR_OK_CENTAVOS:
        return ResultadoConferenciaManual(
            severidade=SeveridadeConferenciaManual.OK,
            mensagem="Total impresso confere com o cálculo das faixas.",
            total_calculado_centavos=calc,
            total_informado_centavos=informado_norm,
            diff_centavos=diff,
        )
    if diff <= LIMIAR_AVISO_CENTAVOS:
        return ResultadoConferenciaManual(
            severidade=SeveridadeConferenciaManual.AVISO,
            mensagem=(
                f"Diferença de {_fmt_reais(diff)} entre o total das faixas "
                f"({_fmt_reais(calc)}) e o total impresso ({_fmt_reais(informado_norm)}). "
                "Confira tipo fiscal e base de preço; divergências pequenas podem ser arredondamento."
            ),
            total_calculado_centavos=calc,
            total_informado_centavos=informado_norm,
            diff_centavos=diff,
        )
    return ResultadoConferenciaManual(
        severidade=SeveridadeConferenciaManual.BLOQUEIO,
        mensagem=(
            f"Total das faixas ({_fmt_reais(calc)}) diverge do total impresso "
            f"({_fmt_reais(informado_norm)}) em {_fmt_reais(diff)}. "
            "O tipo fiscal ou a base de preço podem estar trocados."
        ),
        total_calculado_centavos=calc,
        total_informado_centavos=informado_norm,
        diff_centavos=diff,
    )


def conferir_opcoes_manuais(opcoes: list[OpcaoPropostaRascunho]) -> list[ResultadoConferenciaManual]:
    """Só opções sem extracao_id (entrada manual)."""
    out: list[ResultadoConferenciaManual] = []
    for op in opcoes:
        if op.extracao_id:
            continue
        out.append(conferir_totais_opcao_manual(op))
    return out
