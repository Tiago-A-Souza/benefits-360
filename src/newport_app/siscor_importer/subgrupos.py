"""Montagem de subgrupos sugeridos a partir das linhas."""

from __future__ import annotations

import uuid

from newport_app.models.siscor_import import (
    ImportacaoSiscorCandidata,
    LinhaSiscorCandidata,
    SubgrupoSiscorSugerido,
)


def montar_subgrupos(linhas: list[LinhaSiscorCandidata]) -> list[SubgrupoSiscorSugerido]:
    agrupados: dict[tuple[str, str], SubgrupoSiscorSugerido] = {}
    for linha in linhas:
        if linha.excluida or not linha.plano or not linha.operadora:
            linha.subgrupo_sugerido_id = None
            continue
        chave = (linha.plano, linha.operadora)
        if chave not in agrupados:
            agrupados[chave] = SubgrupoSiscorSugerido(
                id=str(uuid.uuid4()),
                plano_nome=linha.plano,
                operadora=linha.operadora,
            )
        sg = agrupados[chave]
        sg.quantidade_linhas += 1
        linha.subgrupo_sugerido_id = sg.id
    return list(agrupados.values())


def remontar_subgrupos_candidata(candidata: ImportacaoSiscorCandidata) -> None:
    candidata.subgrupos_sugeridos = montar_subgrupos(candidata.linhas)
