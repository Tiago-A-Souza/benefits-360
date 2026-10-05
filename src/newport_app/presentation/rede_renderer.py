"""Renderer HTML estático da aba Rede credenciada."""

from __future__ import annotations

import html

from newport_app.models.presentation import (
    BlocoRedeApresentacao,
    ColunaRedeApresentacao,
    PaginaRedeApresentacao,
    RedeApresentacaoDocumento,
    SecaoRedeApresentacao,
)


def _th_coluna(col: ColunaRedeApresentacao) -> str:
    op = html.escape(col.operadora)
    pl = html.escape(col.plano_nome)
    if col.rede_nao_mapeada:
        pl = "Rede não mapeada"
    return (
        f"<th><span class='op'>{op}</span>"
        f"<span class='pl'>{html.escape(pl)}</span></th>"
    )


def _render_tabela_pagina(pag: PaginaRedeApresentacao) -> str:
    ncols = 1 + len(pag.colunas)
    partes = ["<div class='rolo'><table class='tabela-rede n'><thead><tr>"]
    partes.append("<th>Prestador</th>")
    for col in pag.colunas:
        partes.append(_th_coluna(col))
    partes.append("</tr></thead><tbody>")
    for bloco in pag.blocos:
        partes.append(
            f"<tr class='bloco-rede'><td colspan='{ncols}'>"
            f"{html.escape(bloco.titulo)}"
            f"<span class='q'>{len(bloco.linhas)} prestadores</span></td></tr>"
        )
        for ln in bloco.linhas:
            partes.append("<tr class='p-rede'>")
            partes.append(f"<td class='nm'>{html.escape(ln.prestador)}</td>")
            for col in pag.colunas:
                val = ln.celulas.get(col.chave, "")
                cls = "on" if val else "off"
                partes.append(f"<td class='{cls}'>{html.escape(val)}</td>")
            partes.append("</tr>")
        partes.append(
            f"<tr class='cont-rede'><td>Prestadores cobertos</td>"
        )
        for col in pag.colunas:
            n = bloco.contagem_por_coluna.get(col.chave, 0)
            partes.append(f"<td>{n}</td>")
        partes.append("</tr>")
    partes.append("</tbody></table></div>")
    return "".join(partes)


def _rodape_rede(doc: RedeApresentacaoDocumento) -> str:
    data = html.escape(doc.data_base_rede)
    itens = [
        f"Base SiscorNet atualizada em {data}. A rede credenciada pode ser "
        "alterada pelas operadoras sem aviso prévio.",
        "Este comparativo contempla hospital geral e pronto-socorro credenciados; "
        "não inclui centros clínicos ou consultórios.",
        "Fora de São Paulo, Rio de Janeiro e Distrito Federal, planos Porto Seguro "
        "utilizam a rede Medservice, que não consta nesta extração — a cobertura "
        "pode aparecer vazia por limitação da base, não por falha do sistema.",
    ]
    lis = "".join(f"<li>{html.escape(t)}</li>" for t in itens)
    return (
        "<div class='rede-legenda'>"
        "<p><b>H</b> Hospital Geral · <b>HD</b> Hospital Dia · "
        "<b>M</b> Maternidade · <b>PS</b> Pronto-socorro Geral</p>"
        f"<div class='rede-pontos'><p><b>Pontos de atenção</b></p><ul>{lis}</ul></div>"
        "</div>"
    )


def render_corpo_rede(doc: RedeApresentacaoDocumento) -> str:
    partes: list[str] = []
    for sec in doc.secoes:
        partes.append(f"<div class='secao-rede'><h3 class='secao-rede-tit'>{html.escape(sec.rotulo)}</h3>")
        for i, pag in enumerate(sec.paginas):
            if i > 0:
                partes.append("<div class='quebra-pagina-rede'></div>")
            partes.append(_render_tabela_pagina(pag))
        partes.append("</div>")
    partes.append(_rodape_rede(doc))
    return "".join(partes)


def render_secao_rede_html(sec: SecaoRedeApresentacao, doc: RedeApresentacaoDocumento) -> str:
    del doc
    inner = []
    inner.append(f"<h3 class='secao-rede-tit'>{html.escape(sec.rotulo)}</h3>")
    for i, pag in enumerate(sec.paginas):
        if i > 0:
            inner.append("<div class='quebra-pagina-rede'></div>")
        inner.append(_render_tabela_pagina(pag))
    return "".join(inner)
