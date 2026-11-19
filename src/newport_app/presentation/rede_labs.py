"""Visão de laboratórios do estudo — recorte, marcas e cobertura binária."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from newport_app.presentation.planos_rede import (
    ColunaRede,
    EstadoCasamentoRede,
    TabelaPlanosRedeAliases,
    resolver_casamento_rede,
)
from newport_app.presentation.rede_matriz_laboratorio import (
    BaseRedeLaboratorio,
    PrestadorRedeLaboratorio,
)
from newport_app.presentation.rede_recorte import (
    ModoRecorteGeografico,
    municipios_permitidos,
)
from newport_app.presentation.rede_visao import EstadoMapeamentoPlanoRede
from newport_app.presentation.regras_comerciais import carregar_aliases


@dataclass(frozen=True)
class ColunaLabCasada:
    operadora: str
    plano_nome: str
    estado: EstadoMapeamentoPlanoRede
    col_idx: int | None
    rotulo_coluna: str | None


def casar_planos_laboratorio(
    planos: Iterable[tuple[str, str]],
    colunas: Iterable[ColunaRede],
    tabela: TabelaPlanosRedeAliases,
) -> tuple[ColunaLabCasada, ...]:
    """Mesmo casamento da rede hospitalar — as 189 colunas são idênticas."""
    aliases = carregar_aliases()
    cols = tuple(colunas)
    saida: list[ColunaLabCasada] = []
    for operadora_raw, plano_nome in planos:
        res = resolver_casamento_rede(
            operadora_raw,
            plano_nome,
            cols,
            tabela=tabela,
            aliases=aliases,
        )
        if res.estado == EstadoCasamentoRede.SEM_REDE:
            saida.append(
                ColunaLabCasada(
                    operadora=operadora_raw,
                    plano_nome=plano_nome,
                    estado=EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA,
                    col_idx=None,
                    rotulo_coluna=None,
                )
            )
            continue
        estado = (
            EstadoMapeamentoPlanoRede.ALIAS
            if res.estado == EstadoCasamentoRede.ALIAS
            else EstadoMapeamentoPlanoRede.REGRA
        )
        saida.append(
            ColunaLabCasada(
                operadora=operadora_raw,
                plano_nome=plano_nome,
                estado=estado,
                col_idx=res.col_idx,
                rotulo_coluna=res.rotulo_coluna,
            )
        )
    return tuple(saida)


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
