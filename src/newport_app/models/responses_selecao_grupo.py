"""Respostas HTTP — seleção de planos por grupo de beneficiários (FASE 1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from newport_app.models.responses_remocao import ImpactoRemocao


class PlanoDoGrupo(BaseModel):
    """Um plano do catálogo, avaliado para as vidas de um grupo."""

    opcao_id: str
    plano_nome: str | None = None
    operadora: str | None = None
    acomodacao: str | None = None
    estimado_centavos: int | None = None
    estimado_reais: str | None = None
    diff_centavos: int | None = None
    diff_reais: str | None = None
    escolhido: bool = False


class GrupoSelecaoPlanos(BaseModel):
    subgrupo_id: str
    plano_nome: str
    operadora: str
    quantidade_beneficiarios: int = 0
    referencia_reais: str | None = None
    referencia_rotulo: str | None = None
    selecao_propria: bool = False
    escolhidos: int = 0
    planos: list[PlanoDoGrupo] = Field(default_factory=list)


class SelecaoPlanosGrupoResponse(BaseModel):
    grupos: list[GrupoSelecaoPlanos] = Field(default_factory=list)
    total_catalogo: int = 0


class SalvarSelecaoGrupoRequest(BaseModel):
    subgrupo_id: str
    opcao_ids: list[str] = Field(default_factory=list)
    confirmar_remocoes: bool = False


class SalvarSelecaoGrupoResponse(BaseModel):
    selecao: SelecaoPlanosGrupoResponse
    impacto_remocao: ImpactoRemocao | None = None
