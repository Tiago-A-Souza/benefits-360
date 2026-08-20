"""Confirmação persistida da revisão do comparativo (desbloqueio de Apresentação)."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.adapters.motor_out import motor_result_para_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.compilation import COMPILER_VERSAO
from newport_app.models.draft import ConfirmacaoComparativoRascunho, RascunhoEstudo
from newport_app.models.responses import ComparativoResponse, ConfirmarComparativoResponse
from newport_app.models.snapshot import MOTOR_VERSAO, SNAPSHOT_VERSAO
from newport_app.policy.registry import PolicySetRegistry, default_registry
from newport_app.services.comparativo_ui import ordem_apresentacao_rascunho, salvar_selecao_apresentacao
from newport_app.snapshot.hashing import hash_sha256_objeto, hash_snapshot_canonico
from newport_motor.engine import calcular


class ConfirmacaoComparativoInvalidaError(Exception):
    pass


def rascunho_fingerprint_calc(rascunho: RascunhoEstudo) -> str:
    """Identidade dos dados que afetam o cálculo (exclui seleção/confirmação de UI)."""
    copia = rascunho.model_copy(deep=True)
    copia.selecao_apresentacao = None
    copia.confirmacao_comparativo = None
    return hash_sha256_objeto(copia.model_dump(mode="json"))


def _rascunho_dump_congelamento(rascunho: RascunhoEstudo) -> dict:
    """Rascunho no payload canônico — confirmação é governança, não conteúdo congelado."""
    copia = rascunho.model_copy(deep=True)
    copia.confirmacao_comparativo = None
    return copia.model_dump(mode="json")


def montar_payload_nucleo_congelamento(
    rascunho: RascunhoEstudo,
    policy_registry: PolicySetRegistry,
) -> tuple[ComparativoResponse, dict, bool]:
    """Núcleo 2.8.0 compartilhado pela confirmação e pelo snapshot (inclui a seleção)."""
    resultado = compile(rascunho, policy_registry=policy_registry)
    if not resultado.compilavel:
        from newport_app.services.calculo import RascunhoNaoCompilavelError

        raise RascunhoNaoCompilavelError(resultado)
    assert resultado.compilado is not None
    motor_result = calcular(
        resultado.compilado.estudo_input,
        resultado.compilado.effective_policy,
    )
    comparativo = motor_result_para_comparativo(rascunho, motor_result)
    tem_bloqueio = motor_result.tem_bloqueio or any(
        p.tipo == "bloqueio" for p in comparativo.pendencias
    )
    payload_nucleo = {
        "rascunho": _rascunho_dump_congelamento(rascunho),
        "estudo_input": resultado.compilado.estudo_input.model_dump(mode="json"),
        "effective_policy": resultado.compilado.effective_policy.model_dump(mode="json"),
        "motor_result": motor_result.model_dump(mode="json"),
        "comparativo": comparativo.model_dump(mode="json"),
        "propostas_apresentacao": ordem_apresentacao_rascunho(rascunho),
        "compiler_versao": COMPILER_VERSAO,
        "motor_versao": MOTOR_VERSAO,
        "snapshot_versao": SNAPSHOT_VERSAO,
        "policy_set_versao": rascunho.policy_set_versao,
        "documentos": {
            "siscor": [d.model_dump(mode="json") for d in rascunho.documentos_siscor],
            "cotacao": [d.model_dump(mode="json") for d in rascunho.documentos_cotacao],
        },
    }
    return comparativo, payload_nucleo, tem_bloqueio


def hash_identidade_calculo(
    rascunho: RascunhoEstudo,
    policy_registry: PolicySetRegistry | None = None,
) -> tuple[str, ComparativoResponse]:
    """Token de frescor 2.7.0 — a seleção não entra, para o PUT-então-confirmar da UI."""
    registry = policy_registry or default_registry
    copia = rascunho.model_copy(deep=True)
    copia.selecao_apresentacao = None
    copia.confirmacao_comparativo = None
    comparativo, payload_nucleo, _ = montar_payload_nucleo_congelamento(copia, registry)
    digest = hash_snapshot_canonico(payload_nucleo, versao="2.7.0")
    return digest, comparativo


def hash_comparativo_atual(
    rascunho: RascunhoEstudo,
    policy_registry: PolicySetRegistry | None = None,
) -> tuple[str, ComparativoResponse]:
    """Hash 2.8.0 do congelamento (seleção incluída) — o mesmo do snapshot candidato."""
    registry = policy_registry or default_registry
    comparativo, payload_nucleo, _ = montar_payload_nucleo_congelamento(rascunho, registry)
    digest = hash_snapshot_canonico(payload_nucleo)
    return digest, comparativo


def comparativo_revisao_confirmada(rascunho: RascunhoEstudo) -> bool:
    conf = rascunho.confirmacao_comparativo
    if not conf or not conf.hash_comparativo or not conf.ordem:
        return False
    if conf.rascunho_fingerprint != rascunho_fingerprint_calc(rascunho):
        return False
    validos = {op.id for op in rascunho.opcoes_proposta}
    if not all(op_id in validos for op_id in conf.ordem):
        return False
    if rascunho.selecao_apresentacao and list(rascunho.selecao_apresentacao.ordem) != list(
        conf.ordem
    ):
        return False
    return True


def sanitizar_confirmacao_comparativo(rascunho: RascunhoEstudo) -> None:
    if rascunho.confirmacao_comparativo and not comparativo_revisao_confirmada(rascunho):
        rascunho.confirmacao_comparativo = None


def invalidar_confirmacao_por_selecao(rascunho: RascunhoEstudo) -> None:
    """Mantido para compatibilidade — seleção salva já invalida por padrão."""
    rascunho.confirmacao_comparativo = None


def confirmar_comparativo_revisao(
    rascunho: RascunhoEstudo,
    hash_informado: str | None,
    opcao_ids: list[str],
    policy_registry: PolicySetRegistry | None = None,
) -> ConfirmarComparativoResponse:
    registry = policy_registry or default_registry
    hash_fresco, comparativo = hash_identidade_calculo(rascunho, registry)
    if hash_informado and hash_informado != hash_fresco:
        raise ConfirmacaoComparativoInvalidaError(
            "O comparativo foi alterado — recalcule antes de confirmar."
        )
    if not comparativo.calculo_realizado:
        raise ConfirmacaoComparativoInvalidaError(
            "O cálculo não foi concluído — resolva pendências antes de confirmar."
        )
    if comparativo.consistencia and not comparativo.consistencia.consistente:
        raise ConfirmacaoComparativoInvalidaError(
            comparativo.consistencia.mensagem
            or "Comparativo inconsistente — revise antes de confirmar."
        )
    if not opcao_ids:
        raise ConfirmacaoComparativoInvalidaError(
            "Selecione ao menos uma proposta para a apresentação."
        )

    salvar_selecao_apresentacao(rascunho, opcao_ids, invalidar_confirmacao=False)
    agora = datetime.now(timezone.utc)
    ordem = list(rascunho.selecao_apresentacao.ordem if rascunho.selecao_apresentacao else [])
    digest_congelado, _ = hash_comparativo_atual(rascunho, registry)
    rascunho.confirmacao_comparativo = ConfirmacaoComparativoRascunho(
        opcao_ids=list(ordem),
        ordem=list(ordem),
        hash_comparativo=digest_congelado,
        rascunho_fingerprint=rascunho_fingerprint_calc(rascunho),
        confirmado_em=agora,
    )
    return ConfirmarComparativoResponse(
        hash_comparativo=digest_congelado,
        ordem=list(ordem),
        confirmado_em=agora.isoformat(),
    )
