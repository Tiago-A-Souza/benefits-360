"""Respostas HTTP — extração de cotações PDF."""

from __future__ import annotations

from pydantic import BaseModel, Field

from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, ExtracaoCotacaoCandidata


class MaturidadeExtracaoResponse(BaseModel):
    template_reconhecido: bool = False
    tabela_extraida: bool = False
    valores_reconciliados: bool = False
    proposta_pronta_aplicacao: bool = False
    extracao_financeira_homologada: bool = False
    exige_selecao_consciente: bool = False


class ResultadoImportacaoCotacaoResponse(BaseModel):
    sucesso: bool
    extracao_id: str
    estado: str
    operadora: str | None = None
    template_id: str | None = None
    opcoes_encontradas: int = 0
    alertas: list[AlertaExtracaoCotacao] = Field(default_factory=list)
    maturidade: MaturidadeExtracaoResponse | None = None


class ConfirmacaoExtracaoResponse(BaseModel):
    confirmados: int


class BloqueioOpcaoExtracao(BaseModel):
    opcao_id: str
    plano: str
    motivos: list[str] = Field(default_factory=list)


class AtribuicaoDesfeitaExtracao(BaseModel):
    cenario_id: str
    cenario_rotulo: str
    alvo_id: str
    alvo_rotulo: str
    plano: str


class CenarioIncompletoExtracao(BaseModel):
    cenario_id: str
    cenario_rotulo: str
    alvos_sem_atribuicao: list[str] = Field(default_factory=list)
    ficou_vazio: bool = False


class ImpactoRemocaoExtracao(BaseModel):
    """Planos que a re-aplicação descarta e o que isso desfaz na etapa 4."""

    planos_removidos: list[str] = Field(default_factory=list)
    atribuicoes_desfeitas: list[AtribuicaoDesfeitaExtracao] = Field(default_factory=list)
    cenarios_incompletos: list[CenarioIncompletoExtracao] = Field(default_factory=list)

    @property
    def houve_remocao(self) -> bool:
        return bool(self.planos_removidos)

    @property
    def exige_confirmacao(self) -> bool:
        """Confirmação só quando a remoção derruba atribuição de cenário.

        Remoção sem dano colateral é relatada e aplicada: pedir confirmação nela
        treinaria o operador a passar direto pelo caso que importa.
        """
        return bool(self.atribuicoes_desfeitas)


class AplicarExtracaoResponse(BaseModel):
    opcoes_adicionadas: int
    opcoes_atualizadas: int = 0
    total_opcoes: int
    bloqueios: list[BloqueioOpcaoExtracao] = Field(default_factory=list)
    impacto_remocao: ImpactoRemocaoExtracao | None = None


class AplicarExtracaoRequest(BaseModel):
    confirmar_remocoes: bool = False


class ListaExtracaoCotacaoResponse(BaseModel):
    extracoes: list[ExtracaoCotacaoCandidata] = Field(default_factory=list)


class EstimarPropostasRequest(BaseModel):
    quantidades_por_faixa: dict[int, int] = Field(default_factory=dict)


class EstimarPropostasResponse(BaseModel):
    totais: dict[str, int | None] = Field(default_factory=dict)


class RemoverExtracaoResponse(BaseModel):
    removido: bool = True
    planos_removidos: int = 0
    aprovacao_invalidada: bool = False
    mensagem: str = ""


class DescartarExtracaoRequest(BaseModel):
    motivo: str


class DescartarExtracaoResponse(BaseModel):
    descartada: bool = True
    motivo: str
    planos_removidos: int = 0
    mensagem: str = ""
