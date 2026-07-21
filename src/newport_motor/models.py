"""Modelo de domínio tipado para entrada do motor."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    BaselineEscolhido,
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    PriceBasis,
    RegimeCopartTipo,
    TipoFiscal,
)


class RegimeCopart(BaseModel):
    id: str
    tipo: RegimeCopartTipo
    escopo_procedimentos: list[str] = Field(default_factory=list)
    percentual_bps: int | None = None


class DocumentoCotacao(BaseModel):
    id: str
    operadora: str
    estado_extracao: EstadoExtracao = EstadoExtracao.MANUAL
    parser_versao: str = "manual"


class TabelaPrecoFaixa(BaseModel):
    faixa: int
    valor_centavos: int
    quantidade_cotada: int = 0
    price_basis: PriceBasis = PriceBasis.EXCLUI_IOF
    proveniencia: ProvenienciaCampo = Field(
        default_factory=lambda: ProvenienciaCampo(origem=OrigemValor.MANUAL)
    )


class CustoUnico(BaseModel):
    id: str
    descricao: str
    valor_centavos: int
    proveniencia: ProvenienciaCampo = Field(
        default_factory=lambda: ProvenienciaCampo(origem=OrigemValor.MANUAL)
    )


class OpcaoPlano(BaseModel):
    id: str
    operadora: str
    plano_nome: str
    regime_copart_id: str
    tipo_fiscal: TipoFiscal = TipoFiscal.SEGURADORA
    tabela: list[TabelaPrecoFaixa]
    premio_saude: ComponenteFinanceiro | None = None
    iof: ComponenteFinanceiro | None = None
    total_recorrente: ComponenteFinanceiro | None = None
    total_primeira_parcela: ComponenteFinanceiro | None = None
    custos_unicos: list[CustoUnico] = Field(default_factory=list)
    documento_id: str | None = None


class SubgrupoAtual(BaseModel):
    id: str
    operadora: str
    tipo_fiscal: TipoFiscal
    plano_nome: str
    regime_copart_id: str
    reajuste_bps: int | None = None
    fatura_price_basis: PriceBasis = PriceBasis.DESCONHECIDO
    tabela_atual: list[TabelaPrecoFaixa] = Field(default_factory=list)


class Vida(BaseModel):
    id: str
    nome: str
    nascimento: date
    incluida: bool = True
    subgrupo_atual_id: str | None = None
    valor_fatura_centavos: int | None = None
    faixa_override: int | None = None
    idade_valor_resolvido: bool = False
    idade_valor_override_justificado: bool = False


class AtribuicaoPlano(BaseModel):
    id: str
    alvo_tipo: str  # subgrupo | vida
    alvo_id: str
    opcao_plano_id: str


class Cenario(BaseModel):
    id: str
    rotulo: str | None = None
    baseline_escolhido: BaselineEscolhido | None = None
    atribuicoes: list[AtribuicaoPlano] = Field(default_factory=list)


class EstudoInput(BaseModel):
    id: str
    formato: FormatoEstudo
    vidas: list[Vida]
    subgrupos_atuais: list[SubgrupoAtual] = Field(default_factory=list)
    opcoes_plano: list[OpcaoPlano] = Field(default_factory=list)
    regimes_copart: list[RegimeCopart] = Field(default_factory=list)
    cenarios: list[Cenario] = Field(default_factory=list)
    documentos: list[DocumentoCotacao] = Field(default_factory=list)

    def regime_por_id(self, regime_id: str) -> RegimeCopart | None:
        return next((r for r in self.regimes_copart if r.id == regime_id), None)

    def opcao_por_id(self, opcao_id: str) -> OpcaoPlano | None:
        return next((o for o in self.opcoes_plano if o.id == opcao_id), None)

    def subgrupo_por_id(self, subgrupo_id: str) -> SubgrupoAtual | None:
        return next((s for s in self.subgrupos_atuais if s.id == subgrupo_id), None)

    def vidas_incluidas(self) -> list[Vida]:
        return [v for v in self.vidas if v.incluida]

    def documento_por_id(self, doc_id: str) -> DocumentoCotacao | None:
        return next((d for d in self.documentos if d.id == doc_id), None)
