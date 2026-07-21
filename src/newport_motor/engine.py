"""Ponto de entrada do motor financeiro puro."""

from __future__ import annotations

from newport_motor.calculation import calcular_cenario
from newport_motor.models import EstudoInput
from newport_motor.policy import EffectivePolicy
from newport_motor.reconciliation import reconciliar_opcao
from newport_motor.result import MotorResult
from newport_motor.types import MoneyCents, SeveridadeValidacao
from newport_motor.validations import (
    validar_b03_valores_nao_confirmados,
    validar_b04_idade_valor,
    validar_b05_dados_obrigatorios,
    validar_b06_atribuicoes,
    validar_b07_politica_obrigatoria,
    validar_b08_escopo_piloto,
    validar_price_basis_desconhecido,
)


def calcular(estudo: EstudoInput, policy: EffectivePolicy) -> MotorResult:
    """
    Função pura: (dados_tipados, effective_policy) -> resultado + validações.
    Sem I/O. Mesmo input => mesmo output.
    B-01 (aprovação) é responsabilidade da camada de aplicação.
    """
    validacoes: list = []

    validacoes.extend(validar_b08_escopo_piloto(estudo))
    validacoes.extend(validar_b07_politica_obrigatoria(estudo, policy))
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
    for opcao_id in opcoes_usadas:
        opcao = estudo.opcao_por_id(opcao_id)
        if opcao:
            validacoes.extend(validar_price_basis_desconhecido(opcao))

    if any(v.severidade == SeveridadeValidacao.BLOQUEANTE for v in validacoes):
        return _resultado_parcial(estudo, policy, validacoes)

    cenarios_result: list = []
    for cenario in estudo.cenarios:
        atrib = {a.alvo_id: a.opcao_plano_id for a in cenario.atribuicoes}
        resultado = calcular_cenario(estudo, cenario.id, atrib, policy)
        cenarios_result.append(resultado)

        for secao in resultado.secoes:
            for sg in secao.subgrupos:
                if sg.subtotal_proposta_centavos and sg.opcao_plano_id:
                    opcao = estudo.opcao_por_id(sg.opcao_plano_id)
                    if opcao:
                        validacoes.extend(
                            reconciliar_opcao(
                                opcao,
                                MoneyCents(sg.subtotal_proposta_centavos.centavos),
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
