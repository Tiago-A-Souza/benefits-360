"""Serviço de apresentação HTML a partir de snapshot aprovado."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from newport_app.diagnostico import registrar_evento
from newport_app.models.snapshot import (
    EntregavelApresentacao,
    GerarApresentacaoRequest,
    GerarApresentacaoResponse,
)
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.delivery_storage import LocalFileDeliveryStorage
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html,
    render_html_completo,
)
from newport_app.presentation.motor_por_proposta import PropostaNaoCalculavelError
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.services.comparativo_ui import resolver_propostas_apresentacao_snapshot
from newport_app.services.snapshot import AprovacaoInvalidaError, SnapshotService
from newport_app.snapshot.hashing import hash_sha256_objeto


class ApresentacaoService:
    def __init__(
        self,
        snapshots: SnapshotService,
        repo: SnapshotRepository,
        entregaveis_dir: Path,
    ) -> None:
        self._snapshots = snapshots
        self._repo = repo
        self._entregaveis_dir = entregaveis_dir
        self._storage = LocalFileDeliveryStorage(entregaveis_dir)

    def gerar_html(
        self,
        estudo_id: str,
        snapshot_id: str,
        req: GerarApresentacaoRequest,
    ) -> GerarApresentacaoResponse:
        snap = self._snapshots.obter_snapshot(snapshot_id)
        if snap.estudo_id != estudo_id:
            raise AprovacaoInvalidaError("Snapshot não pertence ao estudo.")
        if snap.estado != "aprovado":
            registrar_evento(
                estudo_id=estudo_id,
                etapa="apresentacao",
                evento="apresentacao_recusada",
                detalhe={"motivo": "snapshot_nao_aprovado", "snapshot_id": snapshot_id},
            )
            raise AprovacaoInvalidaError(
                "Somente snapshots aprovados podem gerar apresentação."
            )
        aprov = self._repo.obter_aprovacao(snapshot_id)
        if aprov is None or aprov.invalidada_em is not None:
            raise AprovacaoInvalidaError("Aprovação inválida ou ausente.")

        propostas = resolver_propostas_apresentacao_snapshot(
            snap.payload,
            req.propostas_selecionadas or None,
        )
        if not propostas:
            raise AprovacaoInvalidaError(
                "Selecione propostas na tela 5 antes de gerar a apresentação."
            )

        if req.modo == "completo":
            vm_resumo = construir_view_model(
                snap,
                modo="resumo",
                propostas_selecionadas=propostas,
                ressalvas=req.ressalvas,
                titulo=req.titulo,
                aprovado_em=aprov.aprovado_em,
            )
            vm_faixas = construir_view_model(
                snap,
                modo="faixas",
                propostas_selecionadas=propostas,
                ressalvas=req.ressalvas,
                titulo=req.titulo,
                aprovado_em=aprov.aprovado_em,
            )
            vm_grupos = construir_view_model(
                snap,
                modo="grupo_familiar",
                propostas_selecionadas=propostas,
                ressalvas=req.ressalvas,
                titulo=req.titulo,
                beneficiarios_agregados=False,
                aprovado_em=aprov.aprovado_em,
            )
            html_content = render_html_completo(vm_resumo, vm_faixas, vm_grupos)
            digest = hash_sha256_objeto(
                {
                    "html": html_content,
                    "modo": "completo",
                    "vm_resumo": vm_resumo.model_dump(mode="json"),
                    "vm_faixas": vm_faixas.model_dump(mode="json"),
                    "vm_grupo_familiar": vm_grupos.model_dump(mode="json"),
                }
            )
            aviso = (
                "O arquivo contém nomes de beneficiários. "
                "Armazene apenas em local privado."
            )
        else:
            vm = construir_view_model(
                snap,
                modo=req.modo,
                propostas_selecionadas=propostas,
                ressalvas=req.ressalvas,
                titulo=req.titulo,
                exibir_todas_faixas=req.exibir_todas_faixas,
                beneficiarios_agregados=(req.modo == "grupo_familiar"),
                aprovado_em=aprov.aprovado_em,
            )
            html_content = render_html(vm)
            digest = hash_sha256_objeto({"html": html_content, "vm": vm.model_dump(mode="json")})
            aviso = None
            if req.modo == "beneficiario":
                aviso = (
                    "O arquivo contém nomes de beneficiários. "
                    "Armazene apenas em local privado."
                )

        nome = f"apresentacao_{req.modo}_{snapshot_id[:8]}.html"
        caminho = self._storage.salvar(
            html_content.encode("utf-8"),
            nome_arquivo=nome,
            estudo_id=estudo_id,
        )
        ent = EntregavelApresentacao(
            id=str(uuid.uuid4()),
            estudo_id=estudo_id,
            snapshot_id=snapshot_id,
            aprovacao_id=aprov.id,
            modo=req.modo,
            propostas_selecionadas=propostas,
            renderer_versao=RENDERER_VERSAO,
            hash_conteudo=digest,
            caminho_arquivo=caminho,
            gerado_em=datetime.now(timezone.utc),
        )
        self._repo.salvar_entregavel(ent)
        rel = str(Path(caminho).relative_to(self._entregaveis_dir))
        return GerarApresentacaoResponse(
            entregavel_id=ent.id,
            caminho_relativo=rel,
            hash_conteudo=digest,
            modo=req.modo,
            aviso_dados_pessoais=aviso,
        )
