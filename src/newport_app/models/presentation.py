"""PresentationViewModel — valores em centavos; formatação só no renderer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PropostaFaixaColuna(BaseModel):
    opcao_id: str
    coluna_id: str = ""
    valor_unitario_centavos: int | None = None
    quantidade: int = 0
    subtotal_centavos: int | None = None


class FaixaApresentacao(BaseModel):
    faixa: int
    rotulo: str
    qtd_titulares: int = 0
    qtd_dependentes: int = 0
    qtd_total: int = 0
    atual_vigente_total_centavos: int | None = None
    atual_vigente_unitario_centavos: int | None = None
    atual_reajustado_total_centavos: int | None = None
    atual_reajustado_unitario_centavos: int | None = None
    observacao_valor: str | None = None
    propostas: list[PropostaFaixaColuna] = Field(default_factory=list)


class CelulaIndicadorResumo(BaseModel):
    """Célula de indicador do resumo — texto ou dinheiro; ausência explícita."""

    texto: str | None = None
    centavos: int | None = None
    bps: int | None = None
    ausente: bool = False
    referencia: bool = False


class LinhaIndicadorResumo(BaseModel):
    """Linha do resumo executivo — nasce do ViewModel, o renderer só exibe."""

    rotulo: str
    atual: CelulaIndicadorResumo | None = None
    propostas: dict[str, CelulaIndicadorResumo] = Field(default_factory=dict)
    destaque: bool = False
    # cabecalho = acima dos planos; rodape = diffs/validade (renovação).
    grupo: str = "cabecalho"


class PropostaApresentacao(BaseModel):
    opcao_id: str
    coluna_id: str = ""
    misto: bool = False
    indice_cenario: int | None = None
    subtotais_por_subgrupo: dict[str, int | None] = Field(default_factory=dict)
    nomes_atribuidos_por_subgrupo: dict[str, str] = Field(default_factory=dict)
    operadoras_participantes: list[str] = Field(default_factory=list)
    operadora: str
    plano_nome: str
    regime_rotulo: str
    regime_tipo: str
    acomodacao: str | None = None
    modalidade: str | None = None
    copart_descricao: str | None = None
    validade: str | None = None
    premio_centavos: int | None = None
    iof_centavos: int | None = None
    total_recorrente_centavos: int | None = None
    total_mensal_centavos: int | None = None
    diff_mensal_centavos: int | None = None
    diff_anual_centavos: int | None = None
    diff_bps: int | None = None


class PlanoAtualApresentacao(BaseModel):
    subgrupo_id: str
    operadora: str
    plano_nome: str
    acomodacao: str | None = None
    modalidade: str | None = None
    copart_descricao: str | None = None
    faixas: list[FaixaApresentacao] = Field(default_factory=list)
    subtotal_vigente_centavos: int | None = None
    subtotal_reajustado_centavos: int | None = None
    reajuste_percentual_exibicao: str | None = None


class BeneficiarioPropostaColuna(BaseModel):
    opcao_id: str
    coluna_id: str = ""
    valor_centavos: int | None = None
    diff_centavos: int | None = None


class BeneficiarioApresentacao(BaseModel):
    vida_id: str
    nome: str
    idade: int | None = None
    faixa: int | None = None
    faixa_rotulo: str | None = None
    parentesco: str | None = None
    plano_atual: str | None = None
    subgrupo_id: str | None = None
    atual_vigente_centavos: int | None = None
    atual_reajustado_centavos: int | None = None
    propostas: list[BeneficiarioPropostaColuna] = Field(default_factory=list)


class GrupoFamiliarApresentacao(BaseModel):
    grupo_id: str
    rotulo: str
    exibir_subtotal: bool = False
    sem_vinculo_resolvido: bool = False
    lista_plana_sem_vinculo: bool = False
    membros: list[BeneficiarioApresentacao] = Field(default_factory=list)
    subtotal_atual_reajustado_centavos: int | None = None
    subtotal_propostas: list[BeneficiarioPropostaColuna] = Field(default_factory=list)


class TotaisSecaoApresentacao(BaseModel):
    atual_centavos: int | None = None
    propostas: dict[str, int | None] = Field(default_factory=dict)
    diff_mensal: dict[str, int | None] = Field(default_factory=dict)
    diff_anual: dict[str, int | None] = Field(default_factory=dict)


class PaginaFaixasApresentacao(BaseModel):
    indice: int
    propostas_ids: list[str] = Field(default_factory=list)


class SecaoRegimeApresentacao(BaseModel):
    regime_rotulo: str
    regime_tipo: str
    propostas: list[PropostaApresentacao] = Field(default_factory=list)
    planos_atuais: list[PlanoAtualApresentacao] = Field(default_factory=list)
    totais: TotaisSecaoApresentacao = Field(default_factory=TotaisSecaoApresentacao)
    paginas_faixas: list[PaginaFaixasApresentacao] = Field(default_factory=list)
    # Indicadores do resumo executivo (acomodação, custo, validade, …) —
    # montados no builder; o renderer itera sem inventar rótulos.
    indicadores_resumo: list[LinhaIndicadorResumo] = Field(default_factory=list)


class TotaisGeraisApresentacao(BaseModel):
    atual_centavos: int | None = None
    propostas: dict[str, int | None] = Field(default_factory=dict)
    diff_mensal: dict[str, int | None] = Field(default_factory=dict)
    diff_anual: dict[str, int | None] = Field(default_factory=dict)
    baseline_rotulo: str | None = None


class PresentationViewModel(BaseModel):
    titulo: str
    subtitulo: str | None = None
    data_apresentacao: str
    estudo_id: str
    modo: str
    formato: str = "renovacao"
    propostas_selecionadas: list[str] = Field(default_factory=list)
    ressalvas: list[str] = Field(default_factory=list)
    avisos_acomodacao: list[str] = Field(default_factory=list)
    avisos_acomodacao_incompleto: list[str] = Field(default_factory=list)
    politicas_provisorias: bool = True
    aviso_rascunho_interno: str = (
        "RASCUNHO INTERNO — políticas provisórias sujeitas a homologação."
    )
    vidas_calculadas: int | None = None
    qtd_planos_vigentes: int | None = None
    totais_gerais: TotaisGeraisApresentacao = Field(default_factory=TotaisGeraisApresentacao)
    secoes_regime: list[SecaoRegimeApresentacao] = Field(default_factory=list)
    beneficiarios: list[BeneficiarioApresentacao] = Field(default_factory=list)
    grupos_familiares: list[GrupoFamiliarApresentacao] = Field(default_factory=list)
    aviso_vinculo_familiar: str | None = None
    reajuste_consolidado_percentual_exibicao: str | None = None
