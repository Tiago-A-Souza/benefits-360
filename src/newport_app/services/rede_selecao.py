"""Seleção de prestadores na etapa 5 (alternativa ao sandbox no HTML)."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo, SelecaoRedeRascunho
from newport_app.models.presentation import (
    BlocoRedeApresentacao,
    RedeApresentacaoDocumento,
    SecaoRedeApresentacao,
)
from newport_app.presentation.rede_apresentacao import contagem_coberturas_bloco


def excluidos_rede(rascunho: RascunhoEstudo) -> set[str]:
    sel = rascunho.selecao_rede
    if not sel or not sel.excluidos:
        return set()
    return set(sel.excluidos)


def sanitizar_selecao_rede(rascunho: RascunhoEstudo, ids_validos: set[str]) -> None:
    sel = rascunho.selecao_rede
    if sel is None:
        return
    excl = [i for i in sel.excluidos if i in ids_validos]
    if not excl and not sel.revisada:
        rascunho.selecao_rede = None
        return
    rascunho.selecao_rede = SelecaoRedeRascunho(
        excluidos=excl,
        revisada=sel.revisada,
    )


def salvar_selecao_rede(
    rascunho: RascunhoEstudo,
    excluidos: list[str],
    *,
    revisada: bool | None = None,
    ids_validos: set[str] | None = None,
) -> SelecaoRedeRascunho:
    atual = rascunho.selecao_rede
    rev = revisada if revisada is not None else (atual.revisada if atual else False)
    limpos: list[str] = []
    vistos: set[str] = set()
    for i in excluidos:
        if i in vistos:
            continue
        if ids_validos is not None and i not in ids_validos:
            continue
        limpos.append(i)
        vistos.add(i)
    if not limpos and not rev:
        rascunho.selecao_rede = None
        return SelecaoRedeRascunho()
    sel = SelecaoRedeRascunho(excluidos=limpos, revisada=rev)
    rascunho.selecao_rede = sel
    return sel


def aplicar_exclusoes_rede_documento(
    doc: RedeApresentacaoDocumento,
    excluidos: set[str],
) -> RedeApresentacaoDocumento:
    if not excluidos:
        return doc
    secoes: list[SecaoRedeApresentacao] = []
    for sec in doc.secoes:
        blocos_novos: list[BlocoRedeApresentacao] = []
        for bloco in sec.blocos:
            linhas = [ln for ln in bloco.linhas if ln.linha_id not in excluidos]
            if not linhas:
                continue
            contagem = contagem_coberturas_bloco(linhas, sec.colunas)
            blocos_novos.append(
                bloco.model_copy(
                    update={
                        "linhas": linhas,
                        "contagem_por_coluna": contagem,
                    }
                )
            )
        paginas = sec.paginas
        if blocos_novos != sec.blocos:
            from newport_app.presentation.rede_apresentacao import _paginas_colunas_rede

            paginas = _paginas_colunas_rede(sec.colunas, blocos_novos)
        total = sum(len(b.linhas) for b in blocos_novos)
        secoes.append(
            sec.model_copy(
                update={
                    "blocos": blocos_novos,
                    "paginas": paginas,
                    "total_linhas": total,
                }
            )
        )
    return doc.model_copy(update={"secoes": secoes})
