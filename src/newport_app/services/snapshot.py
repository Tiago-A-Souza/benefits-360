"""Serviço de snapshot e aprovação."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from newport_app.adapters.motor_out import motor_result_para_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.compilation import COMPILER_VERSAO
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse
from newport_app.models.snapshot import (
    MOTOR_VERSAO,
    AprovacaoSnapshot,
    AprovarSnapshotRequest,
    AprovarSnapshotResponse,
    GerarSnapshotResponse,
    SnapshotCalculo,
)
from newport_app.policy.registry import PolicySetRegistry, default_registry
from newport_app.repository.base import StudyRepository
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.services.calculo import RascunhoNaoCompilavelError
from newport_app.snapshot.hashing import hash_sha256_objeto
from newport_motor.engine import calcular


class SnapshotNaoEncontradoError(Exception):
    pass


class SnapshotBloqueadoError(Exception):
    pass


class AprovacaoInvalidaError(Exception):
    pass


class SnapshotService:
    def __init__(
        self,
        estudos: StudyRepository,
        snapshots: SnapshotRepository,
        historico: HistoricoRepository,
        policy_registry: PolicySetRegistry | None = None,
    ) -> None:
        self._estudos = estudos
        self._snapshots = snapshots
        self._historico = historico
        self._policy_registry = policy_registry or default_registry

    def _compilar_e_calcular(
        self, rascunho: RascunhoEstudo
    ) -> tuple[ComparativoResponse, dict, bool]:
        resultado = compile(rascunho, policy_registry=self._policy_registry)
        if not resultado.compilavel:
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
            "rascunho": rascunho.model_dump(mode="json"),
            "estudo_input": resultado.compilado.estudo_input.model_dump(mode="json"),
            "effective_policy": resultado.compilado.effective_policy.model_dump(mode="json"),
            "motor_result": motor_result.model_dump(mode="json"),
            "comparativo": comparativo.model_dump(mode="json"),
            "compiler_versao": COMPILER_VERSAO,
            "motor_versao": MOTOR_VERSAO,
            "policy_set_versao": rascunho.policy_set_versao,
            "documentos": {
                "siscor": [d.model_dump(mode="json") for d in rascunho.documentos_siscor],
                "cotacao": [d.model_dump(mode="json") for d in rascunho.documentos_cotacao],
            },
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        }
        return comparativo, payload_nucleo, tem_bloqueio

    def gerar_snapshot_candidato(self, estudo_id: str) -> GerarSnapshotResponse:
        rascunho = self._estudos.obter_rascunho(estudo_id)
        if rascunho is None:
            raise ValueError("Estudo não encontrado")
        comparativo, payload, tem_bloqueio = self._compilar_e_calcular(rascunho)
        if tem_bloqueio:
            raise SnapshotBloqueadoError(
                "O comparativo possui bloqueios — resolva pendências antes do snapshot."
            )
        digest = hash_sha256_objeto(payload)
        snap = SnapshotCalculo(
            id=str(uuid.uuid4()),
            estudo_id=estudo_id,
            estado="candidato",
            hash_sha256=digest,
            payload=payload,
            compiler_versao=COMPILER_VERSAO,
            motor_versao=MOTOR_VERSAO,
            policy_set_versao=rascunho.policy_set_versao,
            tem_bloqueio=False,
            criado_em=datetime.now(timezone.utc),
        )
        self._snapshots.salvar_snapshot(snap)
        self._historico.sincronizar_estudo_meta(rascunho)
        self._historico.atualizar_estado_workflow(estudo_id, "em_conferencia")
        self._historico.registrar_auditoria(
            estudo_id,
            entidade="snapshot",
            entidade_id=snap.id,
            acao="gerar_candidato",
            detalhe=f"Hash {digest[:12]}…",
        )
        resumo = {
            "beneficiarios": comparativo.beneficiarios_calculados,
            "totais": comparativo.totais.model_dump() if comparativo.totais else None,
            "secoes": len(comparativo.secoes),
        }
        return GerarSnapshotResponse(
            snapshot_id=snap.id,
            hash_sha256=digest,
            estado=snap.estado,
            tem_bloqueio=False,
            resumo=resumo,
        )

    def obter_snapshot(self, snapshot_id: str) -> SnapshotCalculo:
        snap = self._snapshots.obter_snapshot(snapshot_id)
        if snap is None:
            raise SnapshotNaoEncontradoError(snapshot_id)
        return snap

    def listar_snapshots(self, estudo_id: str) -> list[SnapshotCalculo]:
        return self._snapshots.listar_snapshots(estudo_id)

    def aprovar_snapshot(
        self,
        estudo_id: str,
        snapshot_id: str,
        req: AprovarSnapshotRequest,
    ) -> AprovarSnapshotResponse:
        if not req.confirmo_conteudo:
            raise AprovacaoInvalidaError("Confirme que revisou o conteúdo do snapshot.")
        if not req.revisor_nome.strip():
            raise AprovacaoInvalidaError("Informe o nome do revisor.")
        snap = self.obter_snapshot(snapshot_id)
        if snap.estudo_id != estudo_id:
            raise SnapshotNaoEncontradoError(snapshot_id)
        if snap.estado != "candidato":
            raise AprovacaoInvalidaError("Somente snapshots candidatos podem ser aprovados.")
        auto = req.revisor_nome.strip().lower() in {"auto", "eu", "mesmo"}
        if auto and not req.justificativa:
            raise AprovacaoInvalidaError(
                "Justificativa obrigatória para autoaprovação provisória."
            )
        aprov = AprovacaoSnapshot(
            id=str(uuid.uuid4()),
            snapshot_id=snapshot_id,
            revisor_nome=req.revisor_nome.strip(),
            aprovado_em=datetime.now(timezone.utc),
            justificativa=req.justificativa,
            auto_aprovacao=auto,
        )
        self._snapshots.salvar_aprovacao(aprov)
        self._snapshots.marcar_aprovado(snapshot_id)
        self._historico.atualizar_estado_workflow(estudo_id, "aprovado")
        self._historico.registrar_auditoria(
            estudo_id,
            entidade="aprovacao",
            entidade_id=aprov.id,
            acao="aprovar",
            detalhe=f"Revisor: {aprov.revisor_nome}",
            criado_por=aprov.revisor_nome,
        )
        return AprovarSnapshotResponse(
            aprovacao_id=aprov.id,
            snapshot_id=snapshot_id,
            hash_sha256=snap.hash_sha256,
        )

    def invalidar_por_alteracao(self, estudo_id: str, motivo: str) -> None:
        self._snapshots.invalidar_aprovacoes_estudo(estudo_id, motivo)
        self._historico.atualizar_estado_workflow(estudo_id, "rascunho")
        self._historico.registrar_auditoria(
            estudo_id,
            entidade="estudo",
            entidade_id=estudo_id,
            acao="invalidar_aprovacao",
            detalhe=motivo,
        )

    def comparativo_do_snapshot(self, snapshot_id: str) -> ComparativoResponse:
        snap = self.obter_snapshot(snapshot_id)
        return ComparativoResponse.model_validate(snap.payload["comparativo"])

    def rascunho_do_snapshot(self, snapshot_id: str) -> RascunhoEstudo:
        snap = self.obter_snapshot(snapshot_id)
        return RascunhoEstudo.model_validate(snap.payload["rascunho"])
