"""Modelos da extração de cotações PDF — camada candidata (ETAPA 2.5.5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from newport_app.models.draft import PriceBasisRascunho

PIPELINE_COTACAO_VERSAO = "cotacao-pdf@2.5.5"


class AlertaExtracaoCotacao(BaseModel):
    codigo: str
    mensagem: str
    severidade: Literal["alerta", "bloqueio", "info"] = "alerta"
    pagina: int | None = None


class EvidenciaExtracao(BaseModel):
    pagina: int | None = None
    trecho: str | None = None
    coordenadas: str | None = None


class ValorExtraido(BaseModel):
    id: str
    rotulo: str
    centavos: int | None = None
    texto: str | None = None
    data: date | None = None
    inteiro: int | None = None
    price_basis: PriceBasisRascunho | None = None
    evidencia: EvidenciaExtracao = Field(default_factory=EvidenciaExtracao)
    estado: Literal["confirmar", "revisar", "ausente"] = "ausente"
    confirmado: bool = False
    confirmado_por: str | None = None
    confirmado_em: datetime | None = None
    valor_anterior_centavos: int | None = None
    valor_anterior_texto: str | None = None
    parser_versao: str | None = None
    documento_hash: str | None = None


class FaixaExtraida(BaseModel):
    faixa: int
    valor: ValorExtraido
    quantidade: ValorExtraido


class DivergenciaReconciliacao(BaseModel):
    codigo: str
    descricao: str
    esperado_centavos: int | None = None
    informado_centavos: int | None = None


class ReconciliacaoOpcao(BaseModel):
    subtotal_calculado_centavos: int | None = None
    subtotal_informado_centavos: int | None = None
    total_recorrente_calculado_centavos: int | None = None
    total_recorrente_informado_centavos: int | None = None
    primeira_parcela_calculada_centavos: int | None = None
    primeira_parcela_informada_centavos: int | None = None
    divergencias: list[DivergenciaReconciliacao] = Field(default_factory=list)
    ok: bool = False


class OpcaoCotacaoCandidata(BaseModel):
    id: str
    operadora: ValorExtraido | None = None
    plano_nome: ValorExtraido | None = None
    tipo_fiscal: ValorExtraido | None = None
    acomodacao: ValorExtraido | None = None
    modalidade: ValorExtraido | None = None
    regime_copart: ValorExtraido | None = None
    copart_percentual: ValorExtraido | None = None
    tabela: list[FaixaExtraida] = Field(default_factory=list)
    premio_saude: ValorExtraido | None = None
    iof: ValorExtraido | None = None
    total_recorrente: ValorExtraido | None = None
    total_primeira_parcela: ValorExtraido | None = None
    subtotal_impresso: ValorExtraido | None = None
    custos_unicos: list[ValorExtraido] = Field(default_factory=list)
    validade_oficial: ValorExtraido | None = None
    observacoes: ValorExtraido | None = None
    reconciliacao: ReconciliacaoOpcao | None = None
    excluida: bool = False


class DocumentoCotacaoPDF(BaseModel):
    id: str
    nome_arquivo: str
    hash_sha256: str
    operadora_detectada: str | None = None
    template_id: str | None = None
    parser_versao: str | None = None
    numero_paginas: int = 0


class ExtracaoCotacaoCandidata(BaseModel):
    id: str
    estudo_id: str
    versao: int
    documento: DocumentoCotacaoPDF
    estado: Literal[
        "extraido", "nao_reconhecido", "ocr_pendente", "ocr_parcial", "erro"
    ]
    opcoes: list[OpcaoCotacaoCandidata] = Field(default_factory=list)
    numero_cotacao: ValorExtraido | None = None
    data_emissao: ValorExtraido | None = None
    validade_oficial: ValorExtraido | None = None
    quantidade_vidas_total: ValorExtraido | None = None
    observacoes: ValorExtraido | None = None
    alertas: list[AlertaExtracaoCotacao] = Field(default_factory=list)
    criado_em: datetime
    criado_por: str = "analista-local"
    versoes_anteriores: list[int] = Field(default_factory=list)

    @property
    def campos_extraidos(self) -> list[ValorExtraido]:
        campos: list[ValorExtraido] = []
        for attr in (
            self.numero_cotacao,
            self.data_emissao,
            self.validade_oficial,
            self.quantidade_vidas_total,
            self.observacoes,
        ):
            if attr is not None:
                campos.append(attr)
        for op in self.opcoes:
            for attr in (
                op.operadora,
                op.plano_nome,
                op.tipo_fiscal,
                op.acomodacao,
                op.modalidade,
                op.regime_copart,
                op.copart_percentual,
                op.premio_saude,
                op.iof,
                op.total_recorrente,
                op.total_primeira_parcela,
                op.subtotal_impresso,
                op.validade_oficial,
                op.observacoes,
            ):
                if attr is not None:
                    campos.append(attr)
            for faixa in op.tabela:
                campos.extend([faixa.valor, faixa.quantidade])
            campos.extend(op.custos_unicos)
        return campos
