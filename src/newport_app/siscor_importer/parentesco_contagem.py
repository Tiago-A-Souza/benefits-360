"""Contagem de parentesco nas linhas SISCOR — invariante: soma = total de linhas."""

from __future__ import annotations

from dataclasses import dataclass

from newport_app.models.draft import ParentescoRascunho
from newport_app.models.siscor_import import LinhaSiscorCandidata


@dataclass(frozen=True)
class ContagemParentesco:
    titulares: int = 0
    dependentes: int = 0
    sem_parentesco: int = 0

    @property
    def total(self) -> int:
        return self.titulares + self.dependentes + self.sem_parentesco


def classificar_parentesco_linha(linha: LinhaSiscorCandidata) -> str:
    """Retorna 'titular', 'dependente' ou 'sem_parentesco'."""
    if linha.parentesco == ParentescoRascunho.TITULAR:
        return "titular"
    if linha.parentesco in (
        ParentescoRascunho.CONJUGE,
        ParentescoRascunho.FILHO,
        ParentescoRascunho.COMPANHEIRO,
        ParentescoRascunho.OUTRO,
    ):
        return "dependente"
    texto = (linha.parentesco_texto or "").strip().upper()
    if texto == "TITULAR":
        return "titular"
    if linha.parentesco is None and not texto:
        return "sem_parentesco"
    if linha.parentesco is None:
        return "sem_parentesco"
    return "dependente"


def contar_parentesco(linhas: list[LinhaSiscorCandidata]) -> ContagemParentesco:
    titulares = dependentes = sem = 0
    for linha in linhas:
        cat = classificar_parentesco_linha(linha)
        if cat == "titular":
            titulares += 1
        elif cat == "dependente":
            dependentes += 1
        else:
            sem += 1
    return ContagemParentesco(
        titulares=titulares,
        dependentes=dependentes,
        sem_parentesco=sem,
    )
