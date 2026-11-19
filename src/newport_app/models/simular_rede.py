"""Modelos de resposta do Simular Rede — consulta fora de qualquer estudo."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanoOpcaoSimulacao(BaseModel):
    chave: str
    rotulo: str


class OperadoraOpcaoSimulacao(BaseModel):
    nome: str
    planos: list[PlanoOpcaoSimulacao] = Field(default_factory=list)


class MunicipioOpcaoSimulacao(BaseModel):
    chave: str
    rotulo: str
    zonas: list[str] = Field(default_factory=list)


class UfOpcaoSimulacao(BaseModel):
    uf: str
    municipios: list[MunicipioOpcaoSimulacao] = Field(default_factory=list)


class OpcoesSimulacaoRede(BaseModel):
    data_base_rede: str = ""
    total_prestadores: int = 0
    total_principais: int = 0
    operadoras: list[OperadoraOpcaoSimulacao] = Field(default_factory=list)
    ufs: list[UfOpcaoSimulacao] = Field(default_factory=list)


class ColunaConsultaRede(BaseModel):
    chave: str
    operadora: str
    plano: str


class LinhaConsultaRede(BaseModel):
    linha_id: str
    prestador: str
    prestador_nome: str
    municipio: str
    bairro: str = ""
    zona: str = ""
    zona_sigla: str = ""
    principal: bool = False
    # Texto da coluna `rede_verticalizada` do CSV («Hapvida», «Kora»…); vazio se não é.
    rede_verticalizada: str = ""
    celulas: dict[str, str] = Field(default_factory=dict)
    # Marca agrupada: municípios das unidades no recorte. Vazio nas linhas de hospital.
    municipios: list[str] = Field(default_factory=list)


class BlocoConsultaRede(BaseModel):
    titulo: str
    municipio: str
    linhas: list[LinhaConsultaRede] = Field(default_factory=list)


class ConsultaRedeResponse(BaseModel):
    modo: str
    colunas: list[ColunaConsultaRede] = Field(default_factory=list)
    blocos: list[BlocoConsultaRede] = Field(default_factory=list)
    total_linhas: int = 0
    # Quantos prestadores a consulta alcança antes do corte de «só principais».
    total_encontrado: int = 0
    ocultos_nao_principais: int = 0
    mostrando_todos: bool = False
    # True: volume alto sem filtro geográfico — a lista só vem com `confirmar=true`.
    requer_confirmacao: bool = False
    aviso: str | None = None
    sem_cobertura: bool = False
    data_base_rede: str = ""
    aviso_porto: str | None = None
    contagem_por_coluna: dict[str, int] = Field(default_factory=dict)
