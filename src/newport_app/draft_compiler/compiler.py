"""Compilador estrito RascunhoEstudo → EstudoInput + EffectivePolicy."""

from __future__ import annotations

from newport_app.draft_compiler.mapper import mapear_effective_policy, mapear_estudo_input
from newport_app.draft_compiler.structural import validar_estrutura
from newport_app.models.compilation import (
    COMPILER_VERSAO,
    AvisoCompilacao,
    Compilado,
    ErroCompilacao,
    ResultadoCompilacao,
)
from newport_app.models.draft import RascunhoEstudo
from newport_app.policy.registry import PolicySetRegistry, default_registry


def _avisos_contextuais(rascunho: RascunhoEstudo) -> list[AvisoCompilacao]:
    avisos: list[AvisoCompilacao] = []
    documentos = {d.id: d for d in rascunho.documentos_cotacao}
    for idx, op in enumerate(rascunho.opcoes_proposta):
        if op.documento_cotacao_id is None:
            continue
        doc = documentos.get(op.documento_cotacao_id)
        if doc is not None and doc.validade_oficial is None:
            avisos.append(
                AvisoCompilacao(
                    codigo="APP-AVI-001",
                    caminho=f"/documentos_cotacao/{op.documento_cotacao_id}/validade_oficial",
                    mensagem=(
                        "A validade oficial do documento de cotação vinculado "
                        "ainda não foi informada."
                    ),
                    severidade="alerta",
                )
            )
    return avisos


def compile(
    rascunho: RascunhoEstudo,
    *,
    policy_registry: PolicySetRegistry | None = None,
) -> ResultadoCompilacao:
    registry = policy_registry or default_registry
    erros: list[ErroCompilacao] = list(validar_estrutura(rascunho))

    policy_set = registry.resolve(rascunho.policy_set_versao)
    if policy_set is None:
        erros.append(
            ErroCompilacao(
                codigo="APP-POL-001",
                caminho="/policy_set_versao",
                mensagem=(
                    "A versão de política administrativa informada não está disponível. "
                    "Selecione uma versão reconhecida pelo sistema."
                ),
                severidade="bloqueante",
            )
        )

    if erros:
        return ResultadoCompilacao(
            compilado=None,
            erros=erros,
            avisos=[],
            compiler_versao=COMPILER_VERSAO,
        )

    estudo_input, erros_mapeamento = mapear_estudo_input(rascunho)
    erros.extend(erros_mapeamento)

    policy = mapear_effective_policy(rascunho, policy_set, erros)  # type: ignore[arg-type]

    if erros or estudo_input is None or policy is None:
        return ResultadoCompilacao(
            compilado=None,
            erros=erros,
            avisos=[],
            compiler_versao=COMPILER_VERSAO,
        )

    return ResultadoCompilacao(
        compilado=Compilado(estudo_input=estudo_input, effective_policy=policy),
        erros=[],
        avisos=_avisos_contextuais(rascunho),
        compiler_versao=COMPILER_VERSAO,
    )
