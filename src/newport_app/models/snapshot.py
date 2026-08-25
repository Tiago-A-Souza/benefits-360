"""Snapshot de cálculo e aprovação — ETAPAS 2.7."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MOTOR_VERSAO = "0.1.0"
# 2.7.0 = formato implícito (versão não gravada; hash sem seleção de propostas).
# 2.8.0 = passa a gravar a versão e, na correção seguinte, inclui a seleção no hash.
SNAPSHOT_VERSAO = "2.8.0"


class SnapshotCalculo(BaseModel):
    id: str
    estudo_id: str
    estado: Literal["candidato", "aprovado", "superado"]
    hash_sha256: str
    payload: dict
    compiler_versao: str
    motor_versao: str
    policy_set_versao: str
    snapshot_versao: str | None = None
    tem_bloqueio: bool = False
    criado_em: datetime
    superado_em: datetime | None = None


class AprovacaoSnapshot(BaseModel):
    id: str
    snapshot_id: str
    revisor_nome: str
    aprovado_em: datetime
    justificativa: str | None = None
    auto_aprovacao: bool = False
    invalidada_em: datetime | None = None
    invalidada_motivo: str | None = None


class EntregavelApresentacao(BaseModel):
    id: str
    estudo_id: str
    snapshot_id: str
    aprovacao_id: str
    modo: Literal["faixas", "beneficiario", "resumo", "completo"]
    propostas_selecionadas: list[str] = Field(default_factory=list)
    renderer_versao: str
    hash_conteudo: str
    caminho_arquivo: str
    invalidado: bool = False
    gerado_em: datetime


class GerarSnapshotResponse(BaseModel):
    snapshot_id: str
    hash_sha256: str
    estado: str
    tem_bloqueio: bool
    resumo: dict


class AprovarSnapshotRequest(BaseModel):
    revisor_nome: str
    justificativa: str | None = None
    confirmo_conteudo: bool = False
    auto_aprovacao: bool = False


class AprovarSnapshotResponse(BaseModel):
    aprovacao_id: str
    snapshot_id: str
    hash_sha256: str


class GerarApresentacaoRequest(BaseModel):
    modo: Literal["faixas", "beneficiario", "resumo", "completo"]
    propostas_selecionadas: list[str]
    ressalvas: list[str] = Field(default_factory=list)
    titulo: str | None = None
    exibir_todas_faixas: bool = False


class GerarApresentacaoResponse(BaseModel):
    entregavel_id: str
    caminho_relativo: str
    hash_conteudo: str
    modo: str
    aviso_dados_pessoais: str | None = None
