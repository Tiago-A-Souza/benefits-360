"""Modelos da importação SISCOR — camada candidata (ETAPA 2.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from newport_app.models.draft import ComponenteFinanceiroRascunho, ParentescoRascunho

IMPORTADOR_SISCOR_VERSAO = "siscor@2.5.0"


class DisponibilidadeColunasSiscor(BaseModel):
    """Colunas opcionais presentes no cabeçalho do arquivo (característica do formato)."""

    sexo: bool = False
    cpf_titular: bool = False
    titular: bool = False
    matricula: bool = False
    tipo_de_vida: bool = False
    uf: bool = False
    cidade: bool = False


class ErroArquivoSiscor(BaseModel):
    codigo: str
    mensagem: str
    colunas_faltantes: list[str] = Field(default_factory=list)


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
    sexo_texto: str | None = None
    sexo: str | None = None
    cpf_titular: str | None = None
    titular_nome: str | None = None
    matricula: str | None = None
    tipo_de_vida: str | None = None
    uf: str | None = None
    cidade: str | None = None
    vinculo_grupo_chave: str | None = None
    vinculo_resolvido: bool = False
    editado_manualmente: bool = False
    historico_edicoes: list[EdicaoManualSiscor] = Field(default_factory=list)

    @property
    def tem_excecao(self) -> bool:
        """Alertas informativos (severidade=info) não bloqueiam confirmação."""
        return any(a.severidade != "info" for a in self.alertas)

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
    qtd_titulares: int = 0
    qtd_dependentes: int = 0
    qtd_sem_parentesco: int = 0
    qtd_excluidas: int = 0
    sexo_preenchido: int = 0
    sexo_celula_vazia: int = 0
    localizacao_preenchida: int = 0
    localizacao_celula_vazia: int = 0
    vinculos_resolvidos: int = 0


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
    disponibilidade_colunas: DisponibilidadeColunasSiscor = Field(
        default_factory=DisponibilidadeColunasSiscor
    )
    criado_em: datetime
    criado_por: str = "analista-local"


class ResultadoParseSiscor(BaseModel):
    """Saída do parser — erros de arquivo bloqueiam candidata."""

    sucesso: bool
    erros_arquivo: list[ErroArquivoSiscor] = Field(default_factory=list)
    candidata: ImportacaoSiscorCandidata | None = None
    documento_hash_sha256: str | None = None
