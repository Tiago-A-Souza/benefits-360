"""RascunhoEstudo v1 — DTO canônico da aplicação (não é EstudoInput)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_serializer, model_validator

RASCUNHO_VERSAO_ATUAL = "1.0"


class PriceBasisRascunho(str, Enum):
    INCLUI_IOF = "inclui_iof"
    EXCLUI_IOF = "exclui_iof"
    DESCONHECIDO = "desconhecido"
    NAO_APLICA = "nao_aplica"


class ModalidadeRascunho(str, Enum):
    ADESAO = "adesao"
    COMPULSORIO = "compulsorio"


class ParentescoRascunho(str, Enum):
    TITULAR = "titular"
    CONJUGE = "conjuge"
    FILHO = "filho"
    COMPANHEIRO = "companheiro"
    OUTRO = "outro"


class OrigemValorRascunho(str, Enum):
    MANUAL = "manual"
    EXTRAIDO = "extraido"
    CALCULADO = "calculado"
    IA = "ia"


class ProvenienciaRascunho(BaseModel):
    origem: OrigemValorRascunho = OrigemValorRascunho.MANUAL
    documento_id: str | None = None
    documento_hash: str | None = None
    extrator_versao: str = "manual"
    linha_origem: int | None = None
    celula_origem: str | None = None
    pagina: int | None = None
    evidencia: str | None = None
    coordenadas: str | None = None
    confirmado: bool = False
    confirmado_por: str | None = None
    confirmado_em: datetime | None = None


class ComponenteFinanceiroRascunho(BaseModel):
    centavos: int | None = None
    price_basis: PriceBasisRascunho = PriceBasisRascunho.DESCONHECIDO
    proveniencia: ProvenienciaRascunho = Field(default_factory=ProvenienciaRascunho)

    @field_validator("centavos")
    @classmethod
    def centavos_nao_negativo(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("centavos não pode ser negativo")
        return v


class EmpresaCliente(BaseModel):
    nome: str


class MetadadosPptxRascunho(BaseModel):
    """Reservado para ETAPA 2.8 — sem campos editáveis de governança."""

    titulo_slide: str | None = None
    subtitulo: str | None = None
    data_apresentacao: date | None = None
    template_versao: str | None = None
    operadoras_exibir: list[str] = Field(default_factory=list)


class ObservacoesRascunho(BaseModel):
    notas_analista: str | None = None
    ressalvas_comerciais: str | None = None
    decisoes_pendentes: list[str] = Field(default_factory=list)


class DocumentoCotacaoRascunho(BaseModel):
    id: str
    operadora: str
    validade_oficial: date | None = None
    vigencia_pretendida: date | None = None
    data_emissao: date | None = None
    hash_documento: str | None = Field(default=None, alias="hash")
    parser_versao: str = "manual"
    estado_extracao: Literal["manual", "pendente", "extraido"] = "manual"

    model_config = {"populate_by_name": True}


class DocumentoSiscorRascunho(BaseModel):
    """Planilha SISCOR importada — fonte dos valores extraídos."""

    id: str
    hash_sha256: str
    importador_versao: str
    operadora: str
    versao_importacao: int = 1


class CustoUnicoRascunho(BaseModel):
    id: str
    descricao: str
    valor: ComponenteFinanceiroRascunho


class CampoConfirmavelBaseline(BaseModel):
    valor: Literal["vigente", "reajustado"] | None = None
    confirmado: bool = False


class CampoConfirmavelPrecedencia(BaseModel):
    valor: Literal["tabela_atual", "valor_fatura"] | None = None
    confirmado: bool = False


class EscolhasEstudo(BaseModel):
    data_referencia_idade: date | None = None
    baseline_escolhido: CampoConfirmavelBaseline = Field(
        default_factory=CampoConfirmavelBaseline
    )
    precedencia_atual_vida: CampoConfirmavelPrecedencia = Field(
        default_factory=CampoConfirmavelPrecedencia
    )


class SelecaoApresentacaoRascunho(BaseModel):
    """Propostas escolhidas para apresentação ao cliente (ordem preservada)."""

    opcao_ids: list[str] = Field(default_factory=list)
    ordem: list[str] = Field(default_factory=list)


class IncluidoRedeRascunho(BaseModel):
    """Prestador incluído à mão no ESTUDO (etapa 5): entra na tabela de todas as seções.

    Identifica o prestador pela chave da base de rede (prestador, município,
    bairro normalizado) — o mesmo trio de `_id_linha_rede`. Não tem seção: o
    `linha_id` de cada tabela é derivado do trio + subgrupo. Nunca grava no CSV
    de principais.
    """

    prestador: str
    municipio: str
    bairro: str = ""


class SelecaoRedeRascunho(BaseModel):
    """Prestadores excluídos da aba Rede (etapa 5 — alternativa ao sandbox HTML).

    Grava **exclusões**, não inclusões: prestador novo na base entra marcado por
    padrão (principal) até o corretor excluir. As **inclusões manuais** (hospital
    fora dos principais) são gravadas em `incluidos`, porque são escolha explícita.
    """

    excluidos: list[str] = Field(default_factory=list)
    incluidos: list[IncluidoRedeRascunho] = Field(default_factory=list)
    revisada: bool = False

    @model_serializer(mode="wrap")
    def _omitir_incluidos_vazio(self, handler):
        """Sem inclusões, o JSON é idêntico ao de antes do campo existir.

        O rascunho inteiro entra no conteúdo canônico do snapshot: gravar
        `"incluidos": []` mudaria o hash de todo estudo que já tem seleção.
        """
        dados = handler(self)
        if not self.incluidos:
            dados.pop("incluidos", None)
        return dados


class ConfirmacaoComparativoRascunho(BaseModel):
    """Revisão do comparativo confirmada pelo analista — libera aprovação e exportação."""

    opcao_ids: list[str] = Field(default_factory=list)
    ordem: list[str] = Field(default_factory=list)
    hash_comparativo: str
    rascunho_fingerprint: str
    confirmado_em: datetime


class VidaRascunho(BaseModel):
    id: str
    nome: str
    nascimento: date
    parentesco: ParentescoRascunho | None = None
    sexo: str | None = None
    cpf_titular: str | None = None
    titular_nome: str | None = None
    matricula: str | None = None
    tipo_de_vida: str | None = None
    uf: str | None = None
    cidade: str | None = None
    vinculo_grupo_chave: str | None = None
    incluida: bool = True
    motivo_inclusao: str | None = None
    motivo_exclusao: str | None = None
    subgrupo_atual_id: str | None = None
    valor_fatura: ComponenteFinanceiroRascunho | None = None
    valor_conferencia: ComponenteFinanceiroRascunho | None = None


class TabelaFaixaRascunho(BaseModel):
    faixa: int
    valor_centavos: int
    quantidade_cotada: int | None = None
    price_basis: PriceBasisRascunho
    proveniencia: ProvenienciaRascunho

    @field_validator("valor_centavos")
    @classmethod
    def valor_nao_negativo(cls, v: int) -> int:
        if v < 0:
            raise ValueError("valor_centavos não pode ser negativo")
        return v

    @field_validator("faixa")
    @classmethod
    def faixa_no_intervalo(cls, v: int) -> int:
        if v < 0 or v > 9:
            raise ValueError("faixa deve estar entre 0 e 9")
        return v


class SubgrupoAtualRascunho(BaseModel):
    id: str
    operadora: str
    plano_nome: str
    regime_copart_id: str | None = None
    tipo_fiscal: Literal["seguradora", "operadora"] | None = None
    acomodacao: str | None = None
    modalidade: ModalidadeRascunho | None = None
    reajuste_bps: int | None = None
    fatura_price_basis: PriceBasisRascunho = PriceBasisRascunho.DESCONHECIDO
    subtotal_atual_impresso: ComponenteFinanceiroRascunho | None = None
    tabela_atual: list[TabelaFaixaRascunho] = Field(default_factory=list)


class OpcaoPropostaRascunho(BaseModel):
    id: str
    operadora: str
    plano_nome: str
    regime_copart_id: str | None = None
    tipo_fiscal: Literal["seguradora", "operadora"] | None = None
    acomodacao: str | None = None
    modalidade: ModalidadeRascunho | None = None
    tabela: list[TabelaFaixaRascunho] = Field(default_factory=list)
    premio_saude: ComponenteFinanceiroRascunho | None = None
    iof: ComponenteFinanceiroRascunho | None = None
    total_recorrente: ComponenteFinanceiroRascunho | None = None
    total_primeira_parcela: ComponenteFinanceiroRascunho | None = None
    subtotal_impresso: ComponenteFinanceiroRascunho | None = None
    custos_unicos: list[CustoUnicoRascunho] = Field(default_factory=list)
    documento_cotacao_id: str | None = None
    documentos_origem_ids: list[str] = Field(default_factory=list)
    extracao_id: str | None = None
    extracao_opcao_id: str | None = None
    validade_oficial: date | None = None
    observacoes: str | None = None
    # Entrada manual: totais do PDF ausentes — desliga conferência e exige aviso na UI.
    totais_impressos_nao_constam: bool = False


class AtribuicaoRascunho(BaseModel):
    id: str
    alvo_tipo: Literal["subgrupo", "vida"]
    alvo_id: str
    opcao_plano_id: str


class CenarioRascunho(BaseModel):
    id: str
    rotulo: str | None = None
    atribuicoes: list[AtribuicaoRascunho] = Field(default_factory=list)


class SelecaoPlanosGrupoRascunho(BaseModel):
    """Quais cotações competem com um plano vigente — molde de AtribuicaoRascunho,
    um-para-muitos.

    Ausência de entrada para um subgrupo **não** é seleção vazia: significa «todo
    o catálogo», e é lida assim por `opcoes_do_subgrupo`. Por isso não há default
    preenchido em silêncio no modelo.
    """

    subgrupo_id: str
    opcao_ids: list[str] = Field(default_factory=list)


class RegimeCopartRascunho(BaseModel):
    id: str
    tipo: Literal["sem", "parcial", "percentual"]
    percentual: int | None = None


class RascunhoEstudo(BaseModel):
    rascunho_versao: str
    policy_set_versao: str
    id: str
    titulo: str
    formato: Literal["renovacao", "novo"] = "renovacao"
    empresa_cliente: EmpresaCliente | None = None
    vidas: list[VidaRascunho]
    subgrupos_atuais: list[SubgrupoAtualRascunho] = Field(default_factory=list)
    opcoes_proposta: list[OpcaoPropostaRascunho] = Field(default_factory=list)
    regimes_copart: list[RegimeCopartRascunho] = Field(default_factory=list)
    cenarios: list[CenarioRascunho] = Field(default_factory=list)
    selecao_planos_por_grupo: list[SelecaoPlanosGrupoRascunho] = Field(default_factory=list)
    documentos_cotacao: list[DocumentoCotacaoRascunho] = Field(default_factory=list)
    documentos_siscor: list[DocumentoSiscorRascunho] = Field(default_factory=list)
    escolhas: EscolhasEstudo = Field(default_factory=EscolhasEstudo)
    selecao_apresentacao: SelecaoApresentacaoRascunho | None = None
    selecao_rede: SelecaoRedeRascunho | None = None
    confirmacao_comparativo: ConfirmacaoComparativoRascunho | None = None
    observacoes: ObservacoesRascunho | None = None
    metadados_pptx: MetadadosPptxRascunho | None = None

    @model_validator(mode="after")
    def versao_rascunho_suportada(self) -> RascunhoEstudo:
        if self.rascunho_versao != RASCUNHO_VERSAO_ATUAL:
            raise ValueError(
                f"rascunho_versao '{self.rascunho_versao}' não suportada; "
                f"use '{RASCUNHO_VERSAO_ATUAL}'"
            )
        return self

    def vidas_incluidas(self) -> list[VidaRascunho]:
        return [v for v in self.vidas if v.incluida]


# Aliases de compatibilidade interna (ETAPA 2.1)
SubgrupoRascunho = SubgrupoAtualRascunho
