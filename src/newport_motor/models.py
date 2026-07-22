"""Modelo de domínio tipado para entrada do motor."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    BaselineEscolhido,
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    AlvoTipo,
    PriceBasis,
    RegimeCopartTipo,
    TipoFiscal,
)

FAIXA_MIN = 0
FAIXA_MAX = 9


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

    @field_validator("faixa")
    @classmethod
    def faixa_no_intervalo(cls, v: int) -> int:
        if v < FAIXA_MIN or v > FAIXA_MAX:
            raise ValueError(f"faixa deve estar entre {FAIXA_MIN} e {FAIXA_MAX}")
        return v

    @field_validator("valor_centavos")
    @classmethod
    def valor_nao_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("valor_centavos não pode ser negativo")
        return v


class CustoUnico(BaseModel):
    id: str
    descricao: str
    valor_centavos: int
    proveniencia: ProvenienciaCampo = Field(
        default_factory=lambda: ProvenienciaCampo(origem=OrigemValor.MANUAL)
    )

    @field_validator("valor_centavos")
    @classmethod
    def valor_nao_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("valor_centavos não pode ser negativo")
        return v


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
    subtotal_impresso: ComponenteFinanceiro | None = None
    custos_unicos: list[CustoUnico] = Field(default_factory=list)
    documento_id: str | None = None

    @model_validator(mode="after")
    def validar_tabela_faixas(self) -> OpcaoPlano:
        faixas = [t.faixa for t in self.tabela]
        if len(faixas) != len(set(faixas)):
            raise ValueError(f"faixas duplicadas na opção {self.id}")
        return self


class SubgrupoAtual(BaseModel):
    id: str
    operadora: str
    tipo_fiscal: TipoFiscal
    plano_nome: str
    regime_copart_id: str
    reajuste_bps: int | None = None
    fatura_price_basis: PriceBasis = PriceBasis.DESCONHECIDO
    subtotal_impresso: ComponenteFinanceiro | None = None
    tabela_atual: list[TabelaPrecoFaixa] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_tabela_atual(self) -> SubgrupoAtual:
        faixas = [t.faixa for t in self.tabela_atual]
        if len(faixas) != len(set(faixas)):
            raise ValueError(f"faixas duplicadas na tabela atual do subgrupo {self.id}")
        return self


class Vida(BaseModel):
    id: str
    nome: str
    nascimento: date
    incluida: bool = True
    subgrupo_atual_id: str | None = None
    valor_fatura_centavos: int | None = None
    fatura_price_basis: PriceBasis | None = None
    fatura_proveniencia: ProvenienciaCampo | None = None
    valor_conferencia_centavos: int | None = None
    conferencia_price_basis: PriceBasis | None = None
    faixa_override: int | None = None
    idade_valor_resolvido: bool = False
    idade_valor_override_justificado: bool = False

    @field_validator("valor_fatura_centavos")
    @classmethod
    def fatura_nao_negativa(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("valor_fatura_centavos não pode ser negativo")
        return v

    @field_validator("valor_conferencia_centavos")
    @classmethod
    def conferencia_nao_negativa(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("valor_conferencia_centavos não pode ser negativo")
        return v

    def proveniencia_fatura_efetiva(self) -> ProvenienciaCampo | None:
        if self.valor_fatura_centavos is None:
            return None
        return self.fatura_proveniencia or ProvenienciaCampo(origem=OrigemValor.MANUAL)


class AtribuicaoPlano(BaseModel):
    id: str
    alvo_tipo: AlvoTipo
    alvo_id: str
    opcao_plano_id: str


class Cenario(BaseModel):
    id: str
    rotulo: str | None = None
    baseline_escolhido: BaselineEscolhido | None = None
    atribuicoes: list[AtribuicaoPlano] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_atribuicoes_unicas(self) -> Cenario:
        alvos = [a.alvo_id for a in self.atribuicoes]
        if len(alvos) != len(set(alvos)):
            raise ValueError(f"atribuições duplicadas no cenário {self.id}")
        return self


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

    @model_validator(mode="after")
    def validar_ids_unicos(self) -> EstudoInput:
        _exigir_ids_unicos(self.vidas, "vidas")
        _exigir_ids_unicos(self.subgrupos_atuais, "subgrupos_atuais")
        _exigir_ids_unicos(self.opcoes_plano, "opcoes_plano")
        _exigir_ids_unicos(self.cenarios, "cenarios")
        _exigir_ids_unicos(self.regimes_copart, "regimes_copart")
        _exigir_ids_unicos(self.documentos, "documentos")
        return self


def _exigir_ids_unicos(itens: list, colecao: str) -> None:
    vistos: set[str] = set()
    for item in itens:
        if item.id in vistos:
            raise ValueError(f"ID duplicado em {colecao}: {item.id}")
        vistos.add(item.id)
