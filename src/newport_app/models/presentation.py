"""PresentationViewModel — independente do renderer HTML."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FaixaApresentacao(BaseModel):
    faixa: int
    rotulo: str
    qtd_titulares: int = 0
    qtd_dependentes: int = 0
    qtd_total: int = 0
    atual_vigente_reais: str | None = None
    atual_reajustado_reais: str | None = None
    observacao_valor: str | None = None
    propostas: dict[str, str] = Field(default_factory=dict)


class PropostaApresentacao(BaseModel):
    opcao_id: str
    operadora: str
    plano_nome: str
    regime_rotulo: str
    acomodacao: str | None = None
    modalidade: str | None = None
    validade: str | None = None
    subtotal_reais: str | None = None
    total_mensal_reais: str | None = None
    diff_mensal_reais: str | None = None
    diff_anual_reais: str | None = None


class PlanoAtualApresentacao(BaseModel):
    subgrupo_id: str
    operadora: str
    plano_nome: str
    faixas: list[FaixaApresentacao] = Field(default_factory=list)
    subtotal_reais: str | None = None


class BeneficiarioApresentacao(BaseModel):
    vida_id: str
    nome: str
    idade: int | None = None
    faixa: int | None = None
    faixa_rotulo: str | None = None
    parentesco: str | None = None
    plano_atual: str | None = None
    atual_vigente_reais: str | None = None
    atual_reajustado_reais: str | None = None
    propostas: dict[str, str] = Field(default_factory=dict)
    diff_reais: dict[str, str | None] = Field(default_factory=dict)


class SecaoRegimeApresentacao(BaseModel):
    regime_rotulo: str
    regime_tipo: str
    propostas: list[PropostaApresentacao] = Field(default_factory=list)
    planos_atuais: list[PlanoAtualApresentacao] = Field(default_factory=list)
    totais_atual_reais: str | None = None
    totais_proposta_reais: str | None = None
    diff_mensal_reais: str | None = None
    diff_anual_reais: str | None = None


class PresentationViewModel(BaseModel):
    titulo: str
    subtitulo: str | None = None
    data_apresentacao: str
    estudo_id: str
    modo: str
    snapshot_id: str
    snapshot_hash: str
    renderer_versao: str
    gerado_em: str
    propostas_selecionadas: list[str] = Field(default_factory=list)
    ressalvas: list[str] = Field(default_factory=list)
    politicas_provisorias: bool = True
    totais_gerais: dict[str, str | None] = Field(default_factory=dict)
    secoes_regime: list[SecaoRegimeApresentacao] = Field(default_factory=list)
    beneficiarios: list[BeneficiarioApresentacao] = Field(default_factory=list)
    aviso_rascunho_interno: str = "RASCUNHO INTERNO — políticas provisórias sujeitas a homologação."
