"""Respostas API — importação e conferência SISCOR."""

from __future__ import annotations

from pydantic import BaseModel

from newport_app.models.siscor_import import (
    EstatisticasImportacaoSiscor,
    ErroArquivoSiscor,
    ImportacaoSiscorCandidata,
)
from newport_app.siscor_importer.faixas_cotacao import TabelaFaixasCotacao


class ResumoImportacaoSiscor(BaseModel):
    estudo_id: str
    importacao_id: str | None = None
    versao: int | None = None
    estado: str = "aguardando_conferencia"
    empresa_sugerida: str | None = None
    estatisticas: EstatisticasImportacaoSiscor
    requer_decisao_reimportacao: bool = False
    opcoes_reimportacao: list[str] = []


class ResultadoImportacaoSiscorResponse(BaseModel):
    sucesso: bool
    resumo: ResumoImportacaoSiscor | None = None
    erros_arquivo: list[ErroArquivoSiscor] = []
    candidata: ImportacaoSiscorCandidata | None = None


class ConferenciaSiscorResponse(BaseModel):
    estudo_id: str
    importacao_id: str
    versao: int
    estado: str
    estatisticas: EstatisticasImportacaoSiscor
    linhas: list[dict] = []
    subgrupos_sugeridos: list[dict] = []
    correspondencias_sugeridas: list[dict] = []
    tabela_faixas_cotacao: TabelaFaixasCotacao | None = None
    disponibilidade_colunas: dict | None = None


class ConfirmacaoLoteResponse(BaseModel):
    confirmadas: int
    excecoes_restantes: int
    vidas_no_rascunho: int
    base_aplicada: bool = True
    historico_registrado: bool = True
    repeticao: bool = False
    mensagem: str | None = None
    posicoes_cadastrais: int = 0
    participacoes_historicas: int = 0
