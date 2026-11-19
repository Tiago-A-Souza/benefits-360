"""Visão de laboratórios do estudo — recorte, marcas e cobertura binária."""

from __future__ import annotations

from newport_app.presentation.rede_matriz_laboratorio import (
    BaseRedeLaboratorio,
    PrestadorRedeLaboratorio,
)
from newport_app.presentation.rede_recorte import (
    ModoRecorteGeografico,
    municipios_permitidos,
)


def recortar_laboratorios(
    base: BaseRedeLaboratorio,
    localizacoes: set[tuple[str, str]],
    *,
    modo: ModoRecorteGeografico | None = None,
) -> tuple[frozenset[str], tuple[PrestadorRedeLaboratorio, ...]]:
    """Município das vidas + capital da UF, igual ao hospital. Sem filtro de especialidade."""
    mun_perm = municipios_permitidos(
        localizacoes, set(base.municipios), modo=modo
    )
    prestadores = tuple(
        p for p in base.prestadores if p.chave_municipio in mun_perm
    )
    return frozenset(mun_perm), prestadores
