"""Reconciliação monetária B-02 (P7) — níveis por vida, subtotal e total agregado."""

from __future__ import annotations

from dataclasses import dataclass, field

from newport_motor.finance import (
    componente_para_recorrente,
    primeira_parcela_normalizada,
    recorrente_de_premio_e_iof,
    recorrente_para_primeira_parcela,
)
from newport_motor.models import OpcaoPlano, Vida
from newport_motor.money import abs_diff
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro
from newport_motor.result import Validacao, ValorCalculado
from newport_motor.types import MoneyCents, PriceBasis, SeveridadeValidacao, TipoFiscal


@dataclass
class SubgrupoReconciliacao:
    subgrupo_id: str
    subtotal_atual_calculado_centavos: int | None = None
    subtotal_atual_impresso: ComponenteFinanceiro | None = None
    tipo_fiscal_atual: TipoFiscal | None = None


@dataclass
class DadosReconciliacaoOpcao:
    opcao_id: str
    opcao: OpcaoPlano
    vidas: list[tuple[Vida, int]]  # (vida, proposta_recorrente_calculada)
    subgrupos: list[SubgrupoReconciliacao] = field(default_factory=list)
    total_calculado_centavos: int = 0


def _normalizar_impresso(
    centavos: int,
    basis: PriceBasis,
    tipo_fiscal: TipoFiscal,
    iof_bps: int,
) -> int:
    return int(componente_para_recorrente(centavos, basis, tipo_fiscal, iof_bps))


def _validar_basis_componente(
    comp: ComponenteFinanceiro | None, comp_name: str, opcao_id: str
) -> list[Validacao]:
    if comp is None or comp.centavos is None:
        return []
    if comp.price_basis == PriceBasis.DESCONHECIDO:
        return [
            Validacao(
                codigo="B-02",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem=(
                    f"{comp_name} com price_basis desconhecido (opção {opcao_id}); "
                    "declaração obrigatória (DP-02)."
                ),
                alvo_ref=f"opcao:{opcao_id}:{comp_name}",
            )
        ]
    return []


def reconciliar_opcao_cenario(
    dados: DadosReconciliacaoOpcao,
    policy: EffectivePolicy,
) -> list[Validacao]:
    validacoes: list[Validacao] = []
    opcao = dados.opcao
    tol = policy.tolerancias
    iof_bps = policy.iof_bps
    tf = opcao.tipo_fiscal

    # Bloqueio prévio por basis desconhecido em componentes impressos
    for comp_name, comp in [
        ("premio_saude", opcao.premio_saude),
        ("iof", opcao.iof),
        ("total_recorrente", opcao.total_recorrente),
        ("total_primeira_parcela", opcao.total_primeira_parcela),
        ("subtotal_impresso", opcao.subtotal_impresso),
    ]:
        validacoes.extend(_validar_basis_componente(comp, comp_name, opcao.id))

    if any(v.severidade == SeveridadeValidacao.BLOQUEANTE for v in validacoes):
        return validacoes

    # 1. Por vida (valor de conferência opcional)
    for vida, calc in dados.vidas:
        if vida.valor_conferencia_centavos is None:
            continue
        basis = vida.conferencia_price_basis or PriceBasis.INCLUI_IOF
        if basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"conferencia_price_basis desconhecido (vida {vida.id}).",
                    alvo_ref=f"vida:{vida.id}:conferencia",
                )
            )
            continue
        esperado = _normalizar_impresso(
            vida.valor_conferencia_centavos, basis, tf, int(iof_bps)
        )
        diff = abs(calc - esperado)
        if diff > tol.por_vida_centavos:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Divergência por vida {vida.id}: calculado {calc}c vs "
                        f"conferência {esperado}c (diff {diff}c)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:vida:{vida.id}",
                )
            )

    # 2. Subtotal atual por subgrupo (SubgrupoAtual.subtotal_impresso vs vigente calculado)
    for sg in dados.subgrupos:
        if (
            sg.subtotal_atual_impresso is None
            or sg.subtotal_atual_impresso.centavos is None
            or sg.subtotal_atual_calculado_centavos is None
        ):
            continue
        if sg.subtotal_atual_impresso.price_basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"subtotal_impresso com price_basis desconhecido "
                        f"(subgrupo {sg.subgrupo_id})."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:subgrupo:{sg.subgrupo_id}:subtotal_atual",
                )
            )
            continue
        tf_atual = sg.tipo_fiscal_atual or tf
        esperado = _normalizar_impresso(
            sg.subtotal_atual_impresso.centavos,
            sg.subtotal_atual_impresso.price_basis,
            tf_atual,
            int(iof_bps),
        )
        diff = abs(sg.subtotal_atual_calculado_centavos - esperado)
        if diff > tol.subtotal_centavos:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Subtotal atual subgrupo {sg.subgrupo_id} diverge "
                        f"({sg.subtotal_atual_calculado_centavos}c vs {esperado}c, diff {diff}c)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:subgrupo:{sg.subgrupo_id}:subtotal_atual",
                )
            )

    total_calc = MoneyCents(dados.total_calculado_centavos)

    # 2b. Subtotal da proposta (OpcaoPlano.subtotal_impresso vs total calculado agregado)
    if opcao.subtotal_impresso and opcao.subtotal_impresso.centavos is not None:
        if opcao.subtotal_impresso.price_basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"subtotal_impresso da opção {opcao.id} com price_basis desconhecido."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:subtotal_impresso",
                )
            )
        else:
            esperado_prop = _normalizar_impresso(
                opcao.subtotal_impresso.centavos,
                opcao.subtotal_impresso.price_basis,
                tf,
                int(iof_bps),
            )
            diff = abs(int(total_calc) - esperado_prop)
            if diff > tol.subtotal_centavos:
                validacoes.append(
                    Validacao(
                        codigo="B-02",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Subtotal da proposta diverge do calculado agregado "
                            f"({esperado_prop}c vs {int(total_calc)}c, diff {diff}c)."
                        ),
                        alvo_ref=f"opcao:{opcao.id}:subtotal_proposta",
                    )
                )

    # 3. Prêmio + IOF vs total recorrente (quando componentes existem)
    if (
        opcao.premio_saude
        and opcao.premio_saude.centavos is not None
        and opcao.total_recorrente
        and opcao.total_recorrente.centavos is not None
    ):
        premio_basis = opcao.premio_saude.price_basis
        iof_val = opcao.iof.centavos if opcao.iof else None
        soma_premio_iof = recorrente_de_premio_e_iof(
            opcao.premio_saude.centavos,
            premio_basis,
            iof_val,
            tf,
            iof_bps,
        )
        total_imp = _normalizar_impresso(
            opcao.total_recorrente.centavos,
            opcao.total_recorrente.price_basis,
            tf,
            int(iof_bps),
        )
        diff = abs(soma_premio_iof - total_imp)
        if diff > tol.subtotal_centavos:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Prêmio+IOF ({soma_premio_iof}c) diverge do total recorrente "
                        f"impresso ({total_imp}c, diff {diff}c)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:premio_iof_vs_recorrente",
                )
            )

    # 4. Total calculado vs total recorrente impresso (população agregada da opção)
    if opcao.total_recorrente and opcao.total_recorrente.centavos is not None:
        total_imp = _normalizar_impresso(
            opcao.total_recorrente.centavos,
            opcao.total_recorrente.price_basis,
            tf,
            int(iof_bps),
        )
        diff = abs(int(total_calc) - total_imp)
        if diff > tol.total_centavos:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Total recorrente impresso diverge do calculado agregado "
                        f"({total_imp}c vs {int(total_calc)}c, diff {diff}c)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:total_recorrente",
                )
            )

    # 5. Primeira parcela = total recorrente + custos únicos (bases respeitados)
    if (
        opcao.total_primeira_parcela
        and opcao.total_primeira_parcela.centavos is not None
        and opcao.total_recorrente
        and opcao.total_recorrente.centavos is not None
    ):
        custos = sum(c.valor_centavos for c in opcao.custos_unicos)
        if opcao.total_primeira_parcela.price_basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"total_primeira_parcela com price_basis desconhecido "
                        f"(opção {opcao.id})."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:total_primeira_parcela",
                )
            )
        else:
            if opcao.total_primeira_parcela.centavos < custos:
                validacoes.append(
                    Validacao(
                        codigo="B-02",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Primeira parcela ({opcao.total_primeira_parcela.centavos}c) "
                            f"menor que a soma dos custos únicos ({custos}c) "
                            f"(opção {opcao.id})."
                        ),
                        alvo_ref=f"opcao:{opcao.id}:total_primeira_parcela",
                    )
                )
            else:
                esperado = recorrente_para_primeira_parcela(
                    opcao.total_recorrente.centavos,
                    opcao.total_recorrente.price_basis,
                    custos,
                    tf,
                    iof_bps,
                )
                primeira_equiv = primeira_parcela_normalizada(
                    opcao.total_primeira_parcela.centavos,
                    opcao.total_primeira_parcela.price_basis,
                    custos,
                    tf,
                    iof_bps,
                )
                diff = abs(primeira_equiv - esperado)
                if diff == 0:
                    pass
                elif custos > 0 and diff <= tol.subtotal_centavos:
                    validacoes.append(
                        Validacao(
                            codigo="B-02",
                            severidade=SeveridadeValidacao.ALERTA,
                            mensagem=(
                                f"Primeira parcela com diferença explicável por custos únicos "
                                f"(opção {opcao.id}, diff {diff}c)."
                            ),
                            alvo_ref=f"opcao:{opcao.id}:total_primeira_parcela",
                        )
                    )
                else:
                    severidade = (
                        SeveridadeValidacao.ALERTA
                        if custos > 0 and diff <= tol.total_centavos
                        else SeveridadeValidacao.BLOQUEANTE
                    )
                    validacoes.append(
                        Validacao(
                            codigo="B-02",
                            severidade=severidade,
                            mensagem=(
                                f"Primeira parcela equivalente ({primeira_equiv}c) "
                                f"≠ recorrente + custos únicos ({esperado}c, diff {diff}c)."
                            ),
                            alvo_ref=f"opcao:{opcao.id}:total_primeira_parcela",
                        )
                    )

    return validacoes


def valor_calc(
    centavos: int,
    fontes: list | None = None,
) -> ValorCalculado:
    from newport_motor.provenance import LinhagemReferencia, ProvenienciaCampo
    from newport_motor.types import OrigemValor

    return ValorCalculado(
        centavos=centavos,
        proveniencia=ProvenienciaCampo(
            origem=OrigemValor.CALCULADO,
            extrator_versao="motor@0.1.2",
        ),
        fontes=fontes or [],
    )


def somar_valores(valores: list[ValorCalculado]) -> ValorCalculado:
    from newport_motor.money import add_money
    from newport_motor.provenance import mesclar_fontes

    total = add_money(*[MoneyCents(v.centavos) for v in valores])
    fontes = mesclar_fontes(*[v.fontes for v in valores])
    return valor_calc(int(total), fontes=fontes)
