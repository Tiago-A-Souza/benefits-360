"""Proveniência por campo (IS-04)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from newport_motor.types import OrigemValor, PriceBasis


class ProvenienciaCampo(BaseModel):
    origem: OrigemValor
    documento_id: str | None = None
    extrator_versao: str = "manual"
    evidencia_pagina: int | None = None
    evidencia_trecho: str | None = None
    confirmado: bool = True
    valor_anterior_centavos: int | None = None


class ValorMonetario(BaseModel):
    centavos: int
    price_basis: PriceBasis
    proveniencia: ProvenienciaCampo


class ComponenteFinanceiro(BaseModel):
    """Componente financeiro com basis e proveniência próprios."""

    centavos: int | None = None
    price_basis: PriceBasis
    proveniencia: ProvenienciaCampo = Field(
        default_factory=lambda: ProvenienciaCampo(origem=OrigemValor.CALCULADO)
    )
