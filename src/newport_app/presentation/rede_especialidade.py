"""Filtro de especialidade hospitalar (fase C)."""

from __future__ import annotations

import re

from newport_app.siscor_importer.normalize import normalizar_cabecalho

CODIGOS_ESPECIALIDADE_PERMITIDOS: frozenset[str] = frozenset(
    {"HGER", "HD", "PSGER", "MAT"}
)


def tokens_especialidade_celula(valor: object) -> frozenset[str]:
    if valor is None or str(valor).strip() == "":
        return frozenset()
    norm = normalizar_cabecalho(str(valor))
    partes = re.split(r"[\s\-/]+", norm)
    return frozenset(p for p in partes if p)


def celula_passa_filtro_especialidade(valor: object) -> bool:
    tokens = tokens_especialidade_celula(valor)
    return bool(tokens & CODIGOS_ESPECIALIDADE_PERMITIDOS)


def prestador_passa_filtro_especialidade(celulas: dict[int, object]) -> bool:
    """Mantém se qualquer célula de plano trouxer um dos quatro códigos."""
    return any(celula_passa_filtro_especialidade(v) for v in celulas.values())
