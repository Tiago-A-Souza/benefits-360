"""Reconciliação monetária B-02 (P7)."""

from __future__ import annotations

from newport_motor.models import OpcaoPlano
from newport_motor.money import abs_diff, add_money
from newport_motor.policy import EffectivePolicy, TolerancePolicy
from newport_motor.result import Validacao, ValorCalculado
from newport_motor.types import MoneyCents, PriceBasis, SeveridadeValidacao


def reconciliar_opcao(
    opcao: OpcaoPlano,
    subtotal_calculado_centavos: MoneyCents,
    policy: EffectivePolicy,
) -> list[Validacao]:
    validacoes: list[Validacao] = []
    tol = policy.tolerancias

    if opcao.total_recorrente and opcao.total_recorrente.centavos is not None:
        if opcao.total_recorrente.price_basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"total_recorrente com price_basis desconhecido (opção {opcao.id})."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:total_recorrente",
                )
            )
        else:
            diff = abs_diff(
                MoneyCents(opcao.total_recorrente.centavos),
                subtotal_calculado_centavos,
            )
            if int(diff) > tol.total_centavos:
                validacoes.append(
                    Validacao(
                        codigo="B-02",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Total recorrente impresso diverge do calculado "
                            f"({opcao.total_recorrente.centavos}c vs "
                            f"{int(subtotal_calculado_centavos)}c, diff {int(diff)}c)."
                        ),
                        alvo_ref=f"opcao:{opcao.id}:total_recorrente",
                    )
                )

    if opcao.total_primeira_parcela and opcao.total_primeira_parcela.centavos is not None:
        custos_unicos = sum(c.valor_centavos for c in opcao.custos_unicos)
        esperado = int(subtotal_calculado_centavos) + custos_unicos
        diff = abs(esperado - opcao.total_primeira_parcela.centavos)
        if diff == 0:
            pass
        elif custos_unicos > 0 and diff <= tol.subtotal_centavos:
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
                if custos_unicos > 0 and diff <= tol.total_centavos
                else SeveridadeValidacao.BLOQUEANTE
            )
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=severidade,
                    mensagem=(
                        f"Primeira parcela ({opcao.total_primeira_parcela.centavos}c) "
                        f"≠ recorrente + custos únicos ({esperado}c)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:total_primeira_parcela",
                )
            )

    return validacoes


def reconciliar_por_vida(
    opcao_id: str,
    valores_calculados: list[tuple[str, MoneyCents]],
    valores_esperados: list[tuple[str, MoneyCents | None]],
    tol: TolerancePolicy,
) -> list[Validacao]:
    validacoes: list[Validacao] = []
    esperado_map = {vid: v for vid, v in valores_esperados if v is not None}
    for vida_id, calc in valores_calculados:
        if vida_id in esperado_map:
            diff = abs_diff(calc, esperado_map[vida_id])
            if int(diff) > tol.por_vida_centavos:
                validacoes.append(
                    Validacao(
                        codigo="B-02",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Divergência por vida {vida_id} além da tolerância "
                            f"({int(diff)}c > {tol.por_vida_centavos}c)."
                        ),
                        alvo_ref=f"opcao:{opcao_id}:vida:{vida_id}",
                    )
                )
    return validacoes


def valor_calc(centavos: int) -> ValorCalculado:
    from newport_motor.provenance import ProvenienciaCampo
    from newport_motor.types import OrigemValor

    return ValorCalculado(
        centavos=centavos,
        proveniencia=ProvenienciaCampo(
            origem=OrigemValor.CALCULADO,
            extrator_versao="motor@0.1.0",
        ),
    )


def somar_valores(valores: list[ValorCalculado]) -> ValorCalculado:
    total = add_money(*[MoneyCents(v.centavos) for v in valores])
    return valor_calc(int(total))
