"""Seleção de prestadores na etapa 5 (alternativa ao sandbox no HTML)."""

from __future__ import annotations

from newport_app.models.draft import (
    IncluidoRedeRascunho,
    RascunhoEstudo,
    SelecaoRedeRascunho,
)
from newport_app.models.presentation import (
    BlocoRedeApresentacao,
    RedeApresentacaoDocumento,
    SecaoRedeApresentacao,
)
from newport_app.presentation.rede_apresentacao import (
    _id_linha_rede,
    contagem_coberturas_bloco,
)


def excluidos_rede(rascunho: RascunhoEstudo) -> set[str]:
    sel = rascunho.selecao_rede
    if not sel or not sel.excluidos:
        return set()
    return set(sel.excluidos)


def linha_id_incluido(inc: IncluidoRedeRascunho) -> str:
    """Mesmo `linha_id` da tabela: prestador, município, bairro e subgrupo."""
    return _id_linha_rede(
        inc.prestador, inc.municipio, inc.bairro, subgrupo_id=inc.subgrupo_id
    )


def incluidos_rede(rascunho: RascunhoEstudo) -> list[IncluidoRedeRascunho]:
    sel = rascunho.selecao_rede
    return list(sel.incluidos) if sel and sel.incluidos else []


def descartar_incluidos_invalidos(
    rascunho: RascunhoEstudo,
    chaves_base: set[tuple[str, str, str]] | frozenset[tuple[str, str, str]],
    ids_visao_calculada: set[str] | None = None,
    subgrupos_validos: set[str] | None = None,
) -> None:
    """Valida os `incluidos` contra a base COMPLETA (não contra a visão dos principais).

    Descarta: prestador que sumiu da base; seção que não existe mais; e prestador
    que virou principal do recorte (já está na visão calculada — mantê-lo faria a
    lista crescer e mostraria «Manual» num hospital que virou padrão).
    """
    sel = rascunho.selecao_rede
    if sel is None or not sel.incluidos:
        return
    if subgrupos_validos is None:
        subgrupos_validos = {s.id for s in rascunho.subgrupos_atuais}
    mantidos: list[IncluidoRedeRascunho] = []
    vistos: set[str] = set()
    for inc in sel.incluidos:
        if (inc.prestador, inc.municipio, inc.bairro) not in chaves_base:
            continue
        if inc.subgrupo_id not in subgrupos_validos:
            continue
        lid = linha_id_incluido(inc)
        if lid in vistos:
            continue
        if ids_visao_calculada is not None and lid in ids_visao_calculada:
            continue
        vistos.add(lid)
        mantidos.append(inc)
    if len(mantidos) != len(sel.incluidos):
        rascunho.selecao_rede = sel.model_copy(update={"incluidos": mantidos})


def sanitizar_selecao_rede(
    rascunho: RascunhoEstudo,
    ids_validos: set[str],
    *,
    chaves_base: set[tuple[str, str, str]] | frozenset[tuple[str, str, str]] | None = None,
    ids_visao_calculada: set[str] | None = None,
) -> None:
    """Limpa `excluidos` contra a visão e, se `chaves_base` vier, os `incluidos` contra a base.

    Sem `chaves_base` os `incluidos` passam intactos: por definição eles NÃO estão
    na visão dos principais, e validá-los contra ela os apagaria.
    """
    if chaves_base is not None:
        descartar_incluidos_invalidos(rascunho, chaves_base, ids_visao_calculada)
    sel = rascunho.selecao_rede
    if sel is None:
        return
    excl = [i for i in sel.excluidos if i in ids_validos]
    if not excl and not sel.incluidos and not sel.revisada:
        rascunho.selecao_rede = None
        return
    rascunho.selecao_rede = SelecaoRedeRascunho(
        excluidos=excl,
        incluidos=list(sel.incluidos),
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
    incl = list(atual.incluidos) if atual else []
    limpos: list[str] = []
    vistos: set[str] = set()
    for i in excluidos:
        if i in vistos:
            continue
        if ids_validos is not None and i not in ids_validos:
            continue
        limpos.append(i)
        vistos.add(i)
    if not limpos and not incl and not rev:
        rascunho.selecao_rede = None
        return SelecaoRedeRascunho()
    sel = SelecaoRedeRascunho(excluidos=limpos, incluidos=incl, revisada=rev)
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
