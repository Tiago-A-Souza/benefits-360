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
    proposta_mensal_reais: str
    atual_mensal_reais: str | None = None
    diferenca_mensal_reais: str | None = None
    diferenca_anual_reais: str | None = None
    diferenca_semantica: str | None = None  # aumento | economia | empate
    rotulo_diferenca_mensal: str | None = None
    rotulo_diferenca_anual: str | None = None
    baseline_rotulo: str | None = None


class TotaisComparativoNumerico(BaseModel):
    atual_mensal_centavos: int | None = None
    proposta_mensal_centavos: int | None = None
    diff_mes_centavos: int | None = None
    diff_ano_centavos: int | None = None
    diff_bps: int | None = None
    diferenca_semantica: str | None = None


class PendenciaItem(BaseModel):
    tipo: str  # bloqueio | alerta | info
    titulo: str
    descricao: str
    acao_sugerida: str | None = None
    codigo: str | None = None
    etapa: int | None = None
    quantidade: int = 1
    alvo: str | None = None


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
    quantidade_beneficiarios: int = 0
    valor_mensal_vigente_centavos: int | None = None
    valor_mensal_vigente_reais: str | None = None
    reajuste_bps: int | None = None
    reajuste_percentual_exibicao: str | None = None
    valor_mensal_reajustado_centavos: int | None = None
    valor_mensal_reajustado_reais: str | None = None
    referencia_comparativo: str | None = None
    referencia_comparativo_centavos: int | None = None
    referencia_comparativo_reais: str | None = None
    faixas: list[ResumoFaixaPlanoAtual] = Field(default_factory=list)
    subtotal_calculado_reais: str | None = None
    observacao: str | None = None


class ResumoPlanoAtualResponse(BaseModel):
    planos: list[ResumoPlanoAtualItem] = Field(default_factory=list)
    total_vigente_centavos: int | None = None
    total_vigente_reais: str | None = None
    total_reajustado_centavos: int | None = None
    total_reajustado_reais: str | None = None
    total_calculado_reais: str | None = None
    requer_data_referencia: bool = False
    origem_valores_descricao: str | None = None
    exige_escolha_precedencia: bool = False


class DetalheVidaComparativo(BaseModel):
    vida_id: str
    nome: str
    idade: int | None = None
    faixa: int | None = None
    faixa_rotulo: str | None = None
    parentesco: str | None = None
    plano_atual: str | None = None
    subgrupo_id: str | None = None
    atual_reais: str | None = None
    proposta_reais: str | None = None
    diff_mes_reais: str | None = None
    atual_centavos: int | None = None
    vigente_centavos: int | None = None
    reajustado_centavos: int | None = None
    proposta_centavos: int | None = None
    diff_mes_centavos: int | None = None


class FaixaComparativo(BaseModel):
    faixa: int
    rotulo: str
    quantidade: int
    atual_centavos: int | None = None
    proposta_centavos: int | None = None
    diff_centavos: int | None = None


class PlanoAtualComparativo(BaseModel):
    subgrupo_id: str
    plano_nome: str
    operadora: str
    acomodacao: str | None = None
    regime_coparticipacao: str | None = None
    vidas: int = 0
    vigente_centavos: int | None = None
    reajustado_centavos: int | None = None
    mensal_centavos: int | None = None
    vigente_reais: str | None = None
    reajustado_reais: str | None = None
    mensal_reais: str | None = None
    faixas: list[FaixaPlanoComparativo] = Field(default_factory=list)


class RecorteSubgrupoComparativo(BaseModel):
    subgrupo_id: str
    plano_nome: str
    proposta_centavos: int | None = None
    diff_mes_centavos: int | None = None
    diff_ano_centavos: int | None = None
    diff_bps: int | None = None
    proposta_reais: str | None = None
    diff_mes_reais: str | None = None
    diff_ano_reais: str | None = None


class ColunaFaixaPropostaComparativo(BaseModel):
    opcao_id: str
    unitario_centavos: int | None = None
    quantidade: int = 0
    subtotal_centavos: int | None = None


class FaixaPlanoComparativo(BaseModel):
    faixa: int
    rotulo: str
    quantidade: int = 0
    vigente_unitario_centavos: int | None = None
    vigente_total_centavos: int | None = None
    reajustado_unitario_centavos: int | None = None
    reajustado_total_centavos: int | None = None
    observacao_valor: str | None = None
    propostas: list[ColunaFaixaPropostaComparativo] = Field(default_factory=list)


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


class BloqueioComparativo(BaseModel):
    codigo: str
    mensagem: str
    severidade: str
    alvo_ref: str | None = None
    alvo_rotulo: str | None = None
    etapa_sugerida: int | None = None
    acao_sugerida: str | None = None
    origem: str = "motor"  # compilacao | motor
    mensagem_motor: str | None = None
    quantidade: int = 1
    detalhe_tecnico: str | None = None


class ConsistenciaComparativo(BaseModel):
    propostas_selecionadas: int
    cenarios_configurados: int
    resultados_apresentados: int
    consistente: bool
    mensagem: str | None = None
    mensagem_contagem: str | None = None
    bloqueios: list[BloqueioComparativo] = Field(default_factory=list)


class ResultadoPropostaComparativo(BaseModel):
    opcao_id: str
    cenario_id: str
    plano_nome: str
    operadora: str = ""
    acomodacao: str | None = None
    regime_coparticipacao: str
    regime_tipo: str
    grupo_regime: str  # sem_copart | com_copart
    validade_oficial: str | None = None
    totais: TotaisComparativo | None = None
    numerico: TotaisComparativoNumerico | None = None
    diferenca_percentual: str | None = None
    faixas: list[FaixaComparativo] = Field(default_factory=list)
    destaques: list[str] = Field(default_factory=list)
    secoes: list[SecaoComparativo] = Field(default_factory=list)
    subgrupos: list[RecorteSubgrupoComparativo] = Field(default_factory=list)
    pendencias: list[PendenciaItem] = Field(default_factory=list)
    calculo_realizado: bool = True


class SalvarSelecaoApresentacaoRequest(BaseModel):
    opcao_ids: list[str] = Field(default_factory=list)


class SalvarSelecaoApresentacaoResponse(BaseModel):
    opcao_ids: list[str] = Field(default_factory=list)
    ordem: list[str] = Field(default_factory=list)


class ConfirmarComparativoRequest(BaseModel):
    hash_comparativo: str | None = None
    opcao_ids: list[str] = Field(default_factory=list)


class ConfirmarComparativoResponse(BaseModel):
    hash_comparativo: str
    ordem: list[str] = Field(default_factory=list)
    confirmado_em: str
    snapshot_id: str | None = None


class ComparativoResponse(BaseModel):
    estudo_id: str
    titulo: str
    beneficiarios_calculados: int
    calculo_realizado: bool
    formato: str = "renovacao"
    totais: TotaisComparativo | None = None
    secoes: list[SecaoComparativo] = Field(default_factory=list)
    propostas: list[ResultadoPropostaComparativo] = Field(default_factory=list)
    planos_atuais: list[PlanoAtualComparativo] = Field(default_factory=list)
    faixas_estudo: list[FaixaPlanoComparativo] = Field(default_factory=list)
    propostas_apresentacao: list[str] = Field(default_factory=list)
    consistencia: ConsistenciaComparativo | None = None
    validade_proposta: str | None = None
    pendencias: list[PendenciaItem] = Field(default_factory=list)
    auditoria: list[AuditoriaItem] = Field(default_factory=list)
    hash_comparativo: str | None = None
