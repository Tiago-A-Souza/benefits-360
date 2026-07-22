"""DTO amigável da aplicação — rascunho de estudo (não é EstudoInput)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class VidaRascunho(BaseModel):
    id: str
    nome: str
    nascimento: date
    incluida: bool = True
    subgrupo_atual_id: str | None = None


class TabelaFaixaRascunho(BaseModel):
    faixa: int
    valor_centavos: int
    quantidade_cotada: int = 0


class SubgrupoRascunho(BaseModel):
    id: str
    operadora: str
    plano_nome: str
    regime_copart_id: str
    tipo_fiscal: str = "seguradora"
    reajuste_bps: int | None = None
    fatura_inclui_iof: bool = False
    tabela_atual: list[TabelaFaixaRascunho] = Field(default_factory=list)


class OpcaoPropostaRascunho(BaseModel):
    id: str
    operadora: str
    plano_nome: str
    regime_copart_id: str
    tipo_fiscal: str = "seguradora"
    valores_incluem_iof: bool = False
    tabela: list[TabelaFaixaRascunho] = Field(default_factory=list)


class AtribuicaoRascunho(BaseModel):
    id: str
    alvo_tipo: str
    alvo_id: str
    opcao_plano_id: str


class CenarioRascunho(BaseModel):
    id: str
    rotulo: str | None = None
    atribuicoes: list[AtribuicaoRascunho] = Field(default_factory=list)


class RegimeCopartRascunho(BaseModel):
    id: str
    tipo: str


class EscolhasEstudo(BaseModel):
    """Escolhas do analista — traduzidas para EffectivePolicy no adaptador."""

    data_referencia_idade: date
    valor_atual_referencia: str = "reajustado"  # vigente | reajustado
    prioridade_fatura_ou_tabela: str = "tabela_atual"  # tabela_atual | valor_fatura
    max_beneficiarios_homologados: int | None = 29


class RascunhoEstudo(BaseModel):
    id: str
    titulo: str
    formato: str = "renovacao"
    vidas: list[VidaRascunho]
    subgrupos_atuais: list[SubgrupoRascunho] = Field(default_factory=list)
    opcoes_proposta: list[OpcaoPropostaRascunho] = Field(default_factory=list)
    regimes_copart: list[RegimeCopartRascunho] = Field(default_factory=list)
    cenarios: list[CenarioRascunho] = Field(default_factory=list)
    escolhas: EscolhasEstudo

    def vidas_incluidas(self) -> list[VidaRascunho]:
        return [v for v in self.vidas if v.incluida]
