"""Serviço de snapshot e aprovação."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from newport_app.diagnostico import registrar_evento
from newport_app.models.compilation import COMPILER_VERSAO
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse
from newport_app.models.snapshot import (
    MOTOR_VERSAO,
    SNAPSHOT_VERSAO,
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
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.comparativo import (
    MENSAGEM_FORMATO_ANTERIOR,
    SnapshotFormatoIncompativelError,
    comparativo_em_formato_anterior,
    ler_comparativo_congelado,
)
from newport_app.snapshot.hashing import hash_snapshot_canonico

# Reexportado para os testes e a API que importam deste módulo.
_MENSAGEM_FORMATO_ANTERIOR = MENSAGEM_FORMATO_ANTERIOR


class SnapshotNaoEncontradoError(Exception):
    pass


class SnapshotBloqueadoError(Exception):
    pass


class AprovacaoInvalidaError(Exception):
    pass


def mensagem_bloqueio_snapshot(comparativo: ComparativoResponse) -> str:
    titulos = [p.titulo for p in comparativo.pendencias if p.tipo == "bloqueio" and p.titulo]
    if not titulos:
        return "O comparativo possui bloqueios — resolva pendências antes do snapshot."
    return "Não é possível congelar o comparativo — pendência: " + "; ".join(titulos)


def _dump_aprovacao(aprov: AprovacaoSnapshot | None) -> dict | None:
    if aprov is None:
        return None
    return aprov.model_dump(mode="json")


def _formato_do_snapshot(snap: SnapshotCalculo | None) -> dict:
    """Leitura: não altera estado. Sinaliza comparativo em formato anterior."""
    if snap is None:
        return {"formato_incompativel": False, "mensagem_formato": None}
    bruto = (snap.payload or {}).get("comparativo")
    if comparativo_em_formato_anterior(bruto):
        return {
            "formato_incompativel": True,
            "mensagem_formato": MENSAGEM_FORMATO_ANTERIOR,
        }
    return {"formato_incompativel": False, "mensagem_formato": None}


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
    ) -> tuple[ComparativoResponse, dict, dict, bool]:
        comparativo, payload_nucleo, tem_bloqueio = montar_payload_nucleo_congelamento(
            rascunho, self._policy_registry
        )
        payload = {
            **payload_nucleo,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        }
        return comparativo, payload, payload_nucleo, tem_bloqueio

    def gerar_snapshot_candidato(
        self,
        estudo_id: str,
        rascunho: RascunhoEstudo | None = None,
    ) -> GerarSnapshotResponse:
        if rascunho is None:
            rascunho = self._estudos.obter_rascunho(estudo_id)
        if rascunho is None:
            raise ValueError("Estudo não encontrado")
        comparativo, payload, payload_nucleo, tem_bloqueio = self._compilar_e_calcular(rascunho)
        if tem_bloqueio:
            registrar_evento(
                estudo_id=estudo_id,
                etapa="snapshot",
                evento="snapshot_recusado_bloqueio",
                detalhe={
                    "bloqueios": [
                        p.codigo for p in comparativo.pendencias if p.tipo == "bloqueio"
                    ],
                },
            )
            raise SnapshotBloqueadoError(mensagem_bloqueio_snapshot(comparativo))
        digest = hash_snapshot_canonico(payload_nucleo)
        snap = SnapshotCalculo(
            id=str(uuid.uuid4()),
            estudo_id=estudo_id,
            estado="candidato",
            hash_sha256=digest,
            payload=payload,
            compiler_versao=COMPILER_VERSAO,
            motor_versao=MOTOR_VERSAO,
            policy_set_versao=rascunho.policy_set_versao,
            snapshot_versao=SNAPSHOT_VERSAO,
            tem_bloqueio=False,
            criado_em=datetime.now(timezone.utc),
        )
        # Novo congelamento tira de vigor a aprovação anterior; o histórico permanece.
        self._snapshots.invalidar_aprovacoes_estudo(
            estudo_id, "Novo snapshot candidato gerado"
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

    def status_governanca(self, estudo_id: str) -> dict:
        """Estado que a etapa 5 usa para decidir o que exibir e exportar.

        Somente leitura. Duplicatas de aprovação viva são reparadas na
        migração 2.8.3, não neste GET. Se ainda houver mais de uma, a exibida
        é a de `aprovado_em` mais recente (`snapshot_aprovado_atual`).
        """
        vivo = self._snapshots.snapshot_aprovado_atual(estudo_id)
        candidato = self._snapshots.snapshot_candidato_atual(estudo_id)
        superado = self._snapshots.aprovacao_superada_recente(estudo_id)

        if vivo is not None:
            aprov = self._snapshots.obter_aprovacao(vivo.id)
            return {
                "aprovado": True,
                "estado": "aprovado",
                "snapshot_id": vivo.id,
                "hash_sha256": vivo.hash_sha256,
                "aprovacao": _dump_aprovacao(aprov),
                "candidato_id": candidato.id if candidato else None,
                "superado": None,
                **_formato_do_snapshot(vivo),
            }
        if candidato is not None:
            return {
                "aprovado": False,
                "estado": "candidato",
                "snapshot_id": candidato.id,
                "hash_sha256": candidato.hash_sha256,
                "aprovacao": None,
                "candidato_id": candidato.id,
                "superado": _dump_superado(superado),
                **_formato_do_snapshot(candidato),
            }
        if superado is not None:
            snap, aprov = superado
            return {
                "aprovado": False,
                "estado": "superado",
                "snapshot_id": snap.id,
                "hash_sha256": snap.hash_sha256,
                "aprovacao": _dump_aprovacao(aprov),
                "candidato_id": None,
                "superado": _dump_superado(superado),
                **_formato_do_snapshot(snap),
            }
        return {
            "aprovado": False,
            "estado": None,
            "snapshot_id": None,
            "hash_sha256": None,
            "aprovacao": None,
            "candidato_id": None,
            "superado": None,
            "formato_incompativel": False,
            "mensagem_formato": None,
        }

    def aprovar_snapshot(
        self,
        estudo_id: str,
        snapshot_id: str,
        req: AprovarSnapshotRequest,
    ) -> AprovarSnapshotResponse:
        if not req.confirmo_conteudo:
            registrar_evento(
                estudo_id=estudo_id,
                etapa="apresentacao",
                evento="aprovacao_recusada",
                detalhe={"motivo": "confirmo_conteudo_ausente", "snapshot_id": snapshot_id},
            )
            raise AprovacaoInvalidaError("Confirme que revisou o conteúdo do snapshot.")
        if not req.revisor_nome.strip():
            registrar_evento(
                estudo_id=estudo_id,
                etapa="apresentacao",
                evento="aprovacao_recusada",
                detalhe={"motivo": "revisor_ausente", "snapshot_id": snapshot_id},
            )
            raise AprovacaoInvalidaError("Informe o nome do revisor.")
        snap = self.obter_snapshot(snapshot_id)
        if snap.estudo_id != estudo_id:
            raise SnapshotNaoEncontradoError(snapshot_id)
        if snap.estado != "candidato":
            raise AprovacaoInvalidaError("Somente snapshots candidatos podem ser aprovados.")
        if req.auto_aprovacao and not req.justificativa:
            raise AprovacaoInvalidaError(
                "Justificativa obrigatória para autoaprovação provisória."
            )
        aprov = AprovacaoSnapshot(
            id=str(uuid.uuid4()),
            snapshot_id=snapshot_id,
            revisor_nome=req.revisor_nome.strip(),
            aprovado_em=datetime.now(timezone.utc),
            justificativa=req.justificativa,
            auto_aprovacao=req.auto_aprovacao,
        )
        self._snapshots.superar_aprovacao_em_vigor(
            estudo_id,
            "Nova aprovação em vigor — a anterior foi superada",
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
        rascunho = self._estudos.obter_rascunho(estudo_id)
        if rascunho is not None and rascunho.confirmacao_comparativo is not None:
            rascunho.confirmacao_comparativo = None
            self._estudos.salvar_rascunho(rascunho)
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
        return ler_comparativo_congelado(snap.payload)

    def rascunho_do_snapshot(self, snapshot_id: str) -> RascunhoEstudo:
        snap = self.obter_snapshot(snapshot_id)
        return RascunhoEstudo.model_validate(snap.payload["rascunho"])


def _dump_superado(
    par: tuple[SnapshotCalculo, AprovacaoSnapshot] | None,
) -> dict | None:
    if par is None:
        return None
    snap, aprov = par
    return {
        "snapshot_id": snap.id,
        "hash_sha256": snap.hash_sha256,
        "revisor_nome": aprov.revisor_nome,
        "aprovado_em": aprov.aprovado_em.isoformat(),
        "invalidada_em": aprov.invalidada_em.isoformat() if aprov.invalidada_em else None,
        "invalidada_motivo": aprov.invalidada_motivo,
        "auto_aprovacao": aprov.auto_aprovacao,
    }
