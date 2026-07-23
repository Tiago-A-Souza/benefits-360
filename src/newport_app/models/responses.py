"""Respostas amigáveis para a interface web."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EstudoResumo(BaseModel):
    id: str
    titulo: str
    empresa: str | None = None
    formato: str
    formato_exibicao: str
    beneficiarios_incluidos: int
    beneficiarios_rotulo: str
    descricao: str
    status: str = "em_andamento"
    status_exibicao: str = "Em andamento"
    ultima_alteracao: str | None = None


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
    codigo: str | None = None
    etapa: int | None = None
    quantidade: int = 1


class AuditoriaItem(BaseModel):
    codigo: str
    severidade: str
    mensagem: str
    alvo: str | None = None


class ResumoFaixaPlanoAtual(BaseModel):
    faixa: int
    quantidade_vidas: int
    valor_observado_reais: str | None = None
    alerta_inconsistencia: str | None = None


class ResumoPlanoAtualItem(BaseModel):
    subgrupo_id: str
    operadora: str
    plano_nome: str
    faixas: list[ResumoFaixaPlanoAtual] = Field(default_factory=list)
    subtotal_calculado_reais: str | None = None
    observacao: str | None = None


class ResumoPlanoAtualResponse(BaseModel):
    planos: list[ResumoPlanoAtualItem] = Field(default_factory=list)
    total_calculado_reais: str | None = None
    requer_data_referencia: bool = False


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
