"""Modelos da importação SISCOR — camada candidata (ETAPA 2.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from newport_app.models.draft import ComponenteFinanceiroRascunho, ParentescoRascunho

IMPORTADOR_SISCOR_VERSAO = "siscor@2.3.6"


class ErroArquivoSiscor(BaseModel):
    codigo: str
    mensagem: str


class AlertaLinhaSiscor(BaseModel):
    codigo: str
    caminho: str
    mensagem: str
    severidade: str = "alerta"


class EdicaoManualSiscor(BaseModel):
    campo: str
    valor_anterior: str | None = None
    valor_novo: str | None = None
    editado_em: datetime
    editado_por: str


class CorrespondenciaSugeridaSiscor(BaseModel):
    """Sugestão na reimportação — nunca aplicada automaticamente."""

    linha_nova_id: str
    linha_anterior_id: str | None = None
    motivo: str
    confianca: Literal["baixa", "media"] = "baixa"


class LinhaSiscorCandidata(BaseModel):
    id: str
    numero_linha: int
    celula_origem: str | None = None
    cliente: str | None = None
    segurado: str | None = None
    parentesco_texto: str | None = None
    parentesco: ParentescoRascunho | None = None
    nascimento: str | None = None
    plano: str | None = None
    operadora: str | None = None
    valor_centavos: int | None = None
    valor_fatura: ComponenteFinanceiroRascunho | None = None
    status_texto: str | None = None
    status_normalizado: str | None = None
    incluida_sugerida: bool = False
    alertas: list[AlertaLinhaSiscor] = Field(default_factory=list)
    registro_confirmado: bool = False
    valor_confirmado: bool = False
    confirmado_em: datetime | None = None
    confirmado_por: str | None = None
    subgrupo_sugerido_id: str | None = None
    excluida: bool = False
    motivo_exclusao: str | None = None
    editado_manualmente: bool = False
    historico_edicoes: list[EdicaoManualSiscor] = Field(default_factory=list)

    @property
    def tem_excecao(self) -> bool:
        return bool(self.alertas)

    @property
    def confirmavel(self) -> bool:
        return not self.excluida and not self.tem_excecao


class SubgrupoSiscorSugerido(BaseModel):
    id: str
    plano_nome: str
    operadora: str
    quantidade_linhas: int = 0


class EstatisticasImportacaoSiscor(BaseModel):
    total_linhas_lidas: int = 0
    linhas_utilizaveis: int = 0
    linhas_com_excecao: int = 0
    planos_detectados: int = 0
    confirmadas: int = 0
    aguardando_conferencia: int = 0
    vidas_no_rascunho: int = 0


class ImportacaoSiscorCandidata(BaseModel):
    id: str
    estudo_id: str
    versao: int
    importador_versao: str = IMPORTADOR_SISCOR_VERSAO
    documento_id: str
    documento_hash_sha256: str
    estado: Literal["aguardando_conferencia", "aplicada", "substituida"] = (
        "aguardando_conferencia"
    )
    empresa_sugerida: str | None = None
    linhas: list[LinhaSiscorCandidata] = Field(default_factory=list)
    subgrupos_sugeridos: list[SubgrupoSiscorSugerido] = Field(default_factory=list)
    estatisticas: EstatisticasImportacaoSiscor = Field(
        default_factory=EstatisticasImportacaoSiscor
    )
    correspondencias_sugeridas: list[CorrespondenciaSugeridaSiscor] = Field(
        default_factory=list
    )
    criado_em: datetime
    criado_por: str = "analista-local"


class ResultadoParseSiscor(BaseModel):
    """Saída do parser — erros de arquivo bloqueiam candidata."""

    sucesso: bool
    erros_arquivo: list[ErroArquivoSiscor] = Field(default_factory=list)
    candidata: ImportacaoSiscorCandidata | None = None
    documento_hash_sha256: str | None = None
