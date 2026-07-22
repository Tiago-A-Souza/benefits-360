"""Respostas amigáveis para a interface web."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EstudoResumo(BaseModel):
    id: str
    titulo: str
    formato: str
    beneficiarios_incluidos: int
    descricao: str


class TotaisComparativo(BaseModel):
    atual_mensal_reais: str
    proposta_mensal_reais: str
    diferenca_mensal_reais: str
    diferenca_anual_reais: str
    baseline_rotulo: str


class PendenciaItem(BaseModel):
    tipo: str  # bloqueio | alerta | info
    titulo: str
    descricao: str
    acao_sugerida: str | None = None


class AuditoriaItem(BaseModel):
    codigo: str
    severidade: str
    mensagem: str
    alvo: str | None = None


class ComparativoResponse(BaseModel):
    estudo_id: str
    titulo: str
    beneficiarios_calculados: int
    calculo_realizado: bool
    totais: TotaisComparativo | None = None
    pendencias: list[PendenciaItem] = Field(default_factory=list)
    auditoria: list[AuditoriaItem] = Field(default_factory=list)
