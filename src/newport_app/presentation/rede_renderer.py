"""Renderer HTML estático da aba Rede credenciada."""

from __future__ import annotations

import html

from newport_app.models.presentation import (
    BlocoRedeApresentacao,
    ColunaRedeApresentacao,
    LinhaRedeApresentacao,
    PaginaRedeApresentacao,
    RedeApresentacaoDocumento,
    SecaoRedeApresentacao,
)
from newport_app.presentation.rede_apresentacao import contagem_coberturas_bloco
from newport_app.presentation.rede_avisos import AVISO_REDE_SECAO_SEM_LOCALIZACAO
from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
from newport_app.presentation.rede_codigos import sigla_zona_capital

_CAPITAIS_COM_ZONA = frozenset({"SP.SAO PAULO", "RJ.RIO DE JANEIRO"})


def _th_coluna(col: ColunaRedeApresentacao) -> str:
    if col.rede_nao_mapeada:
        return (
            "<th><span class='op'>Proposta</span>"
            "<span class='pl'>Rede não mapeada</span></th>"
        )
    pl = html.escape(nome_plano_documento(col.plano_nome))
    if col.chave == "rede-atual":
        return (
            f"<th class='atual'><span class='op'>Contrato atual</span>"
            f"<span class='pl'>{pl}</span></th>"
        )
    op = html.escape(col.operadora)
    return f"<th><span class='op'>{op}</span><span class='pl'>{pl}</span></th>"


def _rotulo_prestador(ln: LinhaRedeApresentacao) -> str:
    nome = ln.prestador
    if ln.chave_municipio in _CAPITAIS_COM_ZONA:
        sigla = sigla_zona_capital(ln.zona)
        if sigla:
            nome = f"{sigla} {nome}"
    if ln.bairro:
        return (
            f"{html.escape(nome)}"
            f"<span class='bairro-rede'>{html.escape(ln.bairro)}</span>"
        )
    return html.escape(nome)


def _attrs_linha(ln: LinhaRedeApresentacao) -> str:
    sigla = sigla_zona_capital(ln.zona) if ln.zona else ""
    nome_busca = ln.prestador.lower()
    lid = html.escape(ln.linha_id, quote=True)
    mun = html.escape(ln.chave_municipio, quote=True)
    return (
        f" data-rede-id='{lid}' data-zona='{html.escape(sigla, quote=True)}'"
        f" data-municipio='{mun}' data-nome='{html.escape(nome_busca, quote=True)}'"
    )


def _tr_cabecalho_colunas(pag: PaginaRedeApresentacao, *, classe: str = "") -> str:
    cls = f" class='{classe}'" if classe else ""
    partes = [f"<tr{cls}>"]
    partes.append(
        "<th class='rede-sandbox-check rede-sandbox-js-only' scope='col'>Incl.</th>"
    )
    partes.append("<th scope='col'>Prestador</th>")
    for col in pag.colunas:
        partes.append(_th_coluna(col))
    partes.append("</tr>")
    return "".join(partes)


def _render_tabela_pagina(pag: PaginaRedeApresentacao) -> str:
    ncols = 2 + len(pag.colunas)
    partes = ["<div class='rolo rede-rolo'><table class='tabela-rede n'><thead>"]
    partes.append(_tr_cabecalho_colunas(pag))
    partes.append("</thead><tbody>")
    for i_bloco, bloco in enumerate(pag.blocos):
        partes.append(
            f"<tr class='bloco-rede'><td colspan='{ncols}'>"
            "<div class='bloco-rede-cab'>"
            f"<span class='bloco-rede-tit'>{html.escape(bloco.titulo)}</span>"
            "<span class='bloco-rede-meta'>"
            "<button type='button' class='rede-marcar-bloco rede-sandbox-js-only' "
            "data-checked='1'>Desmarcar bloco</button>"
            f"<span class='q'>{len(bloco.linhas)} prestadores</span>"
            "</span></div></td></tr>"
        )
        # O <thead> já cobre o primeiro bloco; repetir colunas só a partir do 2º município.
        if i_bloco > 0:
            partes.append(_tr_cabecalho_colunas(pag, classe="rede-cab-repetido"))
        for ln in bloco.linhas:
            partes.append(f"<tr class='p-rede'{_attrs_linha(ln)}>")
            partes.append(
                "<td class='rede-sandbox-check rede-sandbox-js-only'>"
                "<input type='checkbox' checked aria-label='Incluir prestador'></td>"
            )
            partes.append(f"<td class='nm'>{_rotulo_prestador(ln)}</td>")
            for col in pag.colunas:
                val = ln.celulas.get(col.chave, "")
                cls = "on" if val else "off"
                partes.append(f"<td class='{cls}'>{html.escape(val)}</td>")
            partes.append("</tr>")
        partes.append(
            f"<tr class='cont-rede'><td colspan='2'>Prestadores cobertos</td>"
        )
        contagem = contagem_coberturas_bloco(bloco.linhas, pag.colunas)
        for col in pag.colunas:
            partes.append(f"<td>{contagem[col.chave]}</td>")
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
    if doc.aviso_sem_localizacao:
        aviso = html.escape(doc.aviso_sem_localizacao)
        partes.append(
            "<div class='aviso-rede-localizacao aviso-vinculo-familiar "
            f"aviso-acomodacao aviso-acomodacao--info'>{aviso}</div>"
        )
    for sec in doc.secoes:
        partes.append(
            f"<div class='secao-rede'><h3 class='secao-rede-tit'>{html.escape(sec.rotulo)}</h3>"
        )
        if sec.sem_localizacao_beneficiarios:
            msg = html.escape(AVISO_REDE_SECAO_SEM_LOCALIZACAO)
            partes.append(
                "<div class='rede-secao-sem-localizacao aviso-acomodacao "
                f"aviso-acomodacao--info'>{msg}</div>"
            )
        else:
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
