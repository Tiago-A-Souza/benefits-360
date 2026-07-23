"""Respostas HTTP — extração de cotações PDF."""

from __future__ import annotations

from pydantic import BaseModel, Field

from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, ExtracaoCotacaoCandidata


class ResultadoImportacaoCotacaoResponse(BaseModel):
    sucesso: bool
    extracao_id: str
    estado: str
    operadora: str | None = None
    template_id: str | None = None
    opcoes_encontradas: int = 0
    alertas: list[AlertaExtracaoCotacao] = Field(default_factory=list)


class ConfirmacaoExtracaoResponse(BaseModel):
    confirmados: int


class AplicarExtracaoResponse(BaseModel):
    opcoes_adicionadas: int
    total_opcoes: int


class ListaExtracaoCotacaoResponse(BaseModel):
    extracoes: list[ExtracaoCotacaoCandidata] = Field(default_factory=list)
