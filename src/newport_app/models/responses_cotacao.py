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


class AplicarExtracaoResponse(BaseModel):
    opcoes_adicionadas: int
    opcoes_atualizadas: int = 0
    total_opcoes: int
    bloqueios: list[BloqueioOpcaoExtracao] = Field(default_factory=list)


class ListaExtracaoCotacaoResponse(BaseModel):
    extracoes: list[ExtracaoCotacaoCandidata] = Field(default_factory=list)


class RemoverExtracaoResponse(BaseModel):
    removido: bool = True
    planos_removidos: int = 0
    aprovacao_invalidada: bool = False
    mensagem: str = ""
