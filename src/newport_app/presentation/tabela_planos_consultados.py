"""Tabela panorâmica — catálogo da etapa 3 × estimativa por grupo."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.presentation import (
    ColunaGrupoConsulta,
    LinhaPlanoConsulta,
    TabelaPlanosConsultados,
)
from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
from newport_app.rascunho.cenarios_sync import subgrupos_com_vidas
from newport_app.rascunho.selecao_grupo import opcoes_do_subgrupo
from newport_app.services.matriz_estimativa import montar_matriz_estimativa
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual


def montar_tabela_planos_consultados(
    rascunho: RascunhoEstudo,
) -> TabelaPlanosConsultados | None:
    """Panorama de consulta: contrato atual + catálogo, sem cálculo novo."""
    if rascunho.formato == "novo":
        return None
    if not rascunho.opcoes_proposta:
        return None

    resumo = montar_resumo_plano_atual(rascunho)
    if not resumo.planos:
        return None

    matriz = montar_matriz_estimativa(rascunho, restrita=False)
    estimado_por_par = {
        (c.opcao_id, c.subgrupo_id): c.estimado_centavos for c in matriz.celulas
    }

    colunas = [
        ColunaGrupoConsulta(subgrupo_id=p.subgrupo_id, rotulo=p.plano_nome)
        for p in resumo.planos
    ]

    linha_atual = LinhaPlanoConsulta(
        plano="Contrato atual",
        operadora="",
        eh_contrato_atual=True,
        celulas={
            p.subgrupo_id: p.valor_mensal_reajustado_centavos for p in resumo.planos
        },
        total_centavos=resumo.total_reajustado_centavos,
    )

    grupos_com_vidas = set(subgrupos_com_vidas(rascunho))
    linhas_opcoes: list[LinhaPlanoConsulta] = []
    ordenacao: list[tuple[LinhaPlanoConsulta, int | None]] = []
    for op in rascunho.opcoes_proposta:
        celulas: dict[str, int | None] = {}
        soma_parcial = 0
        cobre_todos = bool(grupos_com_vidas)
        for col in colunas:
            if op.id not in opcoes_do_subgrupo(rascunho, col.subgrupo_id):
                celulas[col.subgrupo_id] = None
                if col.subgrupo_id in grupos_com_vidas:
                    cobre_todos = False
                continue
            val = estimado_por_par.get((op.id, col.subgrupo_id))
            celulas[col.subgrupo_id] = val
            if val is not None:
                soma_parcial += val
            elif col.subgrupo_id in grupos_com_vidas:
                cobre_todos = False
        linha = LinhaPlanoConsulta(
            plano=nome_plano_documento(op.plano_nome or op.id),
            operadora=(op.operadora or "").strip(),
            celulas=celulas,
            total_centavos=soma_parcial if cobre_todos else None,
        )
        linhas_opcoes.append(linha)
        ordenacao.append((linha, soma_parcial if soma_parcial else None))

    ordenacao.sort(key=lambda par: (par[1] is None, par[1] or 0))
    linhas_opcoes = [lin for lin, _ in ordenacao]

    return TabelaPlanosConsultados(
        colunas=colunas,
        linhas=[linha_atual, *linhas_opcoes],
    )
