"""Entidades de persistência histórica — ETAPA 2.6 + 2.8.1."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Cliente(BaseModel):
    id: str
    nome: str
    criado_em: datetime


class CicloRenovacao(BaseModel):
    id: str
    cliente_id: str
    numero: int
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    criado_em: datetime


class BeneficiarioLogico(BaseModel):
    id: str
    cliente_id: str
    nome: str
    nascimento: date
    parentesco: str | None = None
    sexo: str | None = None
    criado_em: datetime


class EstudoMeta(BaseModel):
    id: str
    titulo: str
    formato: Literal["renovacao", "novo"] = "renovacao"
    cliente_id: str | None = None
    ciclo_id: str | None = None
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
    importacao_id: str | None = None
    criado_em: datetime
    observacao: str | None = None


class BeneficiarioParticipacao(BaseModel):
    id: str
    estudo_id: str
    posicao_versao_id: str
    beneficiario_id: str | None = None
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
    vinculo_status: Literal["pendente", "confirmado", "novo", "rejeitado"] = "pendente"


class SugestaoVinculoBeneficiario(BaseModel):
    participacao_id: str
    sugestao_hash: str
    beneficiario_candidato_id: str | None = None
    confianca: str = "baixa"
    motivo: str


class ConfirmarVinculoRequest(BaseModel):
    participacao_id: str
    acao: Literal["confirmar", "novo", "rejeitar"]
    beneficiario_id: str | None = None


class ConfirmarVinculoLoteRequest(BaseModel):
    participacao_ids: list[str]
    acao: Literal["confirmar_coerentes"]


class VincularEstudoRequest(BaseModel):
    cliente_id: str
    ciclo_id: str | None = None
    criar_ciclo: bool = False
    ciclo_numero: int | None = None


class PlanoContratadoVersao(BaseModel):
    id: str
    estudo_id: str
    ciclo_id: str | None = None
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


class HistoricoEstudoResponse(BaseModel):
    estudo: EstudoMeta
    posicoes: list[PosicaoCadastralVersao] = Field(default_factory=list)
    participacoes: list[BeneficiarioParticipacao] = Field(default_factory=list)
    planos_contratados: list[PlanoContratadoVersao] = Field(default_factory=list)
    ultimo_plano_contratado: PlanoContratadoVersao | None = None
    sugestoes_vinculo: list[SugestaoVinculoBeneficiario] = Field(default_factory=list)
