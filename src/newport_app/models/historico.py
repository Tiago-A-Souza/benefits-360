"""Entidades de persistência histórica — ETAPA 2.6."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class EstudoMeta(BaseModel):
    id: str
    titulo: str
    formato: Literal["renovacao", "novo"] = "renovacao"
    cliente_nome: str | None = None
    ciclo_numero: int = 1
    estado_workflow: Literal[
        "rascunho", "calculado", "em_conferencia", "aprovado"
    ] = "rascunho"
    criado_em: datetime
    atualizado_em: datetime


class PosicaoCadastralVersao(BaseModel):
    id: str
    estudo_id: str
    versao: int
    origem: Literal["siscor", "manual", "seguro_novo"] = "siscor"
    documento_hash: str | None = None
    importador_versao: str | None = None
    criado_em: datetime
    observacao: str | None = None


class BeneficiarioParticipacao(BaseModel):
    id: str
    estudo_id: str
    posicao_versao_id: str
    beneficiario_logico_id: str
    vida_rascunho_id: str
    nome: str
    nascimento: date
    parentesco: str | None = None
    sexo: str | None = None
    status: Literal["incluido", "excluido"] = "incluido"
    subgrupo_id: str | None = None
    plano_nome: str | None = None
    faixa: int | None = None
    valor_centavos: int | None = None
    motivo_alteracao: str | None = None
    sugestao_vinculo: str | None = None


class PlanoContratadoVersao(BaseModel):
    id: str
    estudo_id: str
    opcao_proposta_id: str
    operadora: str
    plano_nome: str
    vigencia_inicio: date
    vigencia_fim: date | None = None
    acomodacao: str | None = None
    modalidade: str | None = None
    regime_copart: str | None = None
    copart_percentual: int | None = None
    premio_centavos: int | None = None
    iof_centavos: int | None = None
    total_recorrente_centavos: int | None = None
    tabela_json: str
    documento_origem_id: str | None = None
    criado_em: datetime
    criado_por: str = "analista-local"


class RegistrarPlanoContratadoRequest(BaseModel):
    opcao_proposta_id: str
    vigencia_inicio: date
    vigencia_fim: date | None = None
    acomodacao: str | None = None
    modalidade: str | None = None
    regime_copart: str | None = None
    copart_percentual: int | None = None
    documento_origem_id: str | None = None


class AuditoriaEvento(BaseModel):
    id: str
    estudo_id: str
    entidade: str
    entidade_id: str | None = None
    acao: str
    detalhe: str | None = None
    criado_em: datetime
    criado_por: str = "analista-local"
