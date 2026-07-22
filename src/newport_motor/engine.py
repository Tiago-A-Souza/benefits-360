"""Ponto de entrada do motor financeiro puro."""

from __future__ import annotations

from newport_motor.calculation import agregar_por_opcao_no_cenario, calcular_cenario
from newport_motor.models import EstudoInput
from newport_motor.policy import EffectivePolicy
from newport_motor.reconciliation import (
    DadosReconciliacaoOpcao,
    SubgrupoReconciliacao,
    reconciliar_opcao_cenario,
)
from newport_motor.result import MotorResult
from newport_motor.types import SeveridadeValidacao
from newport_motor.validations import (
    validar_b03_valores_nao_confirmados,
    validar_b04_idade_valor,
    validar_b05_dados_obrigatorios,
    validar_b06_atribuicoes,
    validar_b07_politica_obrigatoria,
    validar_b08_escopo_piloto,
    validar_entrada_estrutural,
)


def calcular(estudo: EstudoInput, policy: EffectivePolicy) -> MotorResult:
    """
    Função pura: (dados_tipados, effective_policy) -> resultado + validações.
    B-01 (aprovação) é responsabilidade da camada de aplicação.
    """
    validacoes: list = []

    validacoes.extend(validar_b08_escopo_piloto(estudo))
    validacoes.extend(validar_b07_politica_obrigatoria(estudo, policy))
    validacoes.extend(validar_entrada_estrutural(estudo))
    validacoes.extend(validar_b03_valores_nao_confirmados(estudo))
    validacoes.extend(validar_b06_atribuicoes(estudo))

    if any(v.severidade == SeveridadeValidacao.BLOQUEANTE for v in validacoes):
        return _resultado_parcial(estudo, policy, validacoes)

    validacoes.extend(
        validar_b04_idade_valor(estudo, policy, policy.tolerancias.por_vida_centavos)
    )

    opcoes_usadas: set[str] = set()
    for cenario in estudo.cenarios:
        for atr in cenario.atribuicoes:
            opcoes_usadas.add(atr.opcao_plano_id)

    validacoes.extend(validar_b05_dados_obrigatorios(estudo, opcoes_usadas))

    if any(v.severidade == SeveridadeValidacao.BLOQUEANTE for v in validacoes):
        return _resultado_parcial(estudo, policy, validacoes)

    cenarios_result: list = []
    for cenario in estudo.cenarios:
        atrib = {a.alvo_id: a.opcao_plano_id for a in cenario.atribuicoes}
        resultado = calcular_cenario(estudo, cenario.id, atrib, policy)
        cenarios_result.append(resultado)

        agregado = agregar_por_opcao_no_cenario(estudo, cenario.id, atrib, resultado)
        for opcao_id, dados in agregado.items():
            opcao = estudo.opcao_por_id(opcao_id)
            if opcao is None:
                continue

            total_calc = dados["total"]

            subgrupos_rec = [
                SubgrupoReconciliacao(
                    subgrupo_id=sg["subgrupo_id"],
                    subtotal_calculado_centavos=sg["subtotal"],
                    subtotal_impresso=sg["subtotal_impresso"],
                )
                for sg in dados["subgrupos"]
            ]

            validacoes.extend(
                reconciliar_opcao_cenario(
                    DadosReconciliacaoOpcao(
                        opcao_id=opcao_id,
                        opcao=opcao,
                        vidas=dados["vidas"],
                        subgrupos=subgrupos_rec,
                        total_calculado_centavos=total_calc,
                    ),
                    policy,
                )
            )

    bloqueios = sorted({v.codigo for v in validacoes if v.severidade == SeveridadeValidacao.BLOQUEANTE})
    return MotorResult(
        estudo_id=estudo.id,
        cenarios=cenarios_result,
        validacoes=validacoes,
        politicas_efetivas=policy.as_snapshot_dict(),
        bloqueios_abertos=bloqueios,
    )


def _resultado_parcial(
    estudo: EstudoInput,
    policy: EffectivePolicy,
    validacoes: list,
) -> MotorResult:
    bloqueios = sorted({v.codigo for v in validacoes if v.severidade == SeveridadeValidacao.BLOQUEANTE})
    return MotorResult(
        estudo_id=estudo.id,
        cenarios=[],
        validacoes=validacoes,
        politicas_efetivas=policy.as_snapshot_dict(),
        bloqueios_abertos=bloqueios,
    )
