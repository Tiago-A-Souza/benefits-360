"""Respostas amigáveis para a interface web."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EstudoResumo(BaseModel):
    id: str
    titulo: str
    formato: str
    formato_exibicao: str
    beneficiarios_incluidos: int
    beneficiarios_rotulo: str
    descricao: str


class TotaisComparativo(BaseModel):
    atual_mensal_reais: str
    proposta_mensal_reais: str
    diferenca_mensal_reais: str
    diferenca_anual_reais: str
    diferenca_semantica: str  # aumento | economia | empate
    rotulo_diferenca_mensal: str
    rotulo_diferenca_anual: str
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


class DetalheVidaComparativo(BaseModel):
    vida_id: str
    nome: str
    idade: int | None = None
    faixa: int | None = None
    parentesco: str | None = None
    plano_atual: str | None = None
    atual_reais: str | None = None
    proposta_reais: str | None = None
    diff_mes_reais: str | None = None


class SecaoComparativo(BaseModel):
    rotulo: str
    regime_tipo: str
    atual_mensal_reais: str | None = None
    proposta_mensal_reais: str | None = None
    diferenca_mensal_reais: str | None = None
    diferenca_anual_reais: str | None = None
    diferenca_semantica: str | None = None
    rotulo_diferenca_mensal: str | None = None
    vidas: list[DetalheVidaComparativo] = Field(default_factory=list)


class ComparativoResponse(BaseModel):
    estudo_id: str
    titulo: str
    beneficiarios_calculados: int
    calculo_realizado: bool
    totais: TotaisComparativo | None = None
    secoes: list[SecaoComparativo] = Field(default_factory=list)
    validade_proposta: str | None = None
    pendencias: list[PendenciaItem] = Field(default_factory=list)
    auditoria: list[AuditoriaItem] = Field(default_factory=list)
