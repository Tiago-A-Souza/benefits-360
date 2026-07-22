"""Proveniência por campo (IS-04)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from newport_motor.types import OrigemValor, PriceBasis


class LinhagemReferencia(BaseModel):
    """Referência não recursiva à fonte de entrada usada em um valor calculado."""

    alvo_ref: str
    origem: OrigemValor
    documento_id: str | None = None
    extrator_versao: str | None = None


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

    @field_validator("centavos")
    @classmethod
    def centavos_nao_negativo(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("centavos não pode ser negativo")
        return v


def linhagem_de_proveniencia(alvo_ref: str, prov: ProvenienciaCampo) -> LinhagemReferencia:
    return LinhagemReferencia(
        alvo_ref=alvo_ref,
        origem=prov.origem,
        documento_id=prov.documento_id,
        extrator_versao=prov.extrator_versao,
    )


def mesclar_fontes(*listas: list[LinhagemReferencia]) -> list[LinhagemReferencia]:
    vistos: set[str] = set()
    resultado: list[LinhagemReferencia] = []
    for lista in listas:
        for fonte in lista:
            if fonte.alvo_ref in vistos:
                continue
            vistos.add(fonte.alvo_ref)
            resultado.append(fonte)
    return resultado
