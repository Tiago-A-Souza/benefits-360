"""Renderer HTML autocontido — identidade Newport (sem metadados técnicos no cliente)."""

from __future__ import annotations

import html

from newport_app.models.presentation import (
    FaixaApresentacao,
    PlanoAtualApresentacao,
    PresentationViewModel,
    PropostaApresentacao,
    SecaoRegimeApresentacao,
)
from newport_app.presentation.branding import (
    lema_newport,
    logo_data_uri,
    poppins_font_face_css,
    rotulo_consultoria,
    site_newport,
)
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA
from newport_app.presentation.formatacao import formatar_data_br, formatar_reais

RENDERER_VERSAO = "html@2.10.0"


def _cel(valor: int | None) -> str:
    if valor is None:
        return ""
    return html.escape(formatar_reais(valor))


def _cel_diff(valor: int | None) -> str:
    if valor is None:
        return ""
    texto = html.escape(formatar_reais(valor))
    if valor < 0:
        return f"<span class='neg'>{texto}</span>"
    if valor > 0:
        return f"<span class='pos'>{texto}</span>"
    return texto


def _cel_diff_ou_referencia(valor: int | None) -> str:
    """Diferença zero (proposta mais barata / única) → «referência», não R$ 0,00."""
    if valor is None:
        return ""
    if valor == 0:
        return "referência"
    return _cel_diff(valor)

def _cel_contrato_atual(
    reajustado_centavos: int | None,
    percentual: str | None,
) -> str:
    """Documento: só reajustado + percentual; vigente não aparece."""
    if reajustado_centavos is None and not percentual:
        return ""
    valor = _cel(reajustado_centavos)
    if percentual:
        return f"{valor}<span class='ajuste'>{html.escape(percentual)}</span>"
    return valor


def _meta_proposta(prop: PropostaApresentacao) -> str:
    partes = [
        f"<strong>{html.escape(prop.operadora)} — {html.escape(prop.plano_nome)}</strong>",
    ]
    if prop.acomodacao:
        partes.append(f"Acomodação: {html.escape(prop.acomodacao)}")
    if prop.modalidade:
        partes.append(f"Modalidade: {html.escape(prop.modalidade)}")
    if prop.copart_descricao:
        partes.append(f"Coparticipação: {html.escape(prop.copart_descricao)}")
    if prop.validade:
        validade = formatar_data_br(prop.validade) or prop.validade
        partes.append(f"Validade: {html.escape(validade)}")
    if prop.premio_centavos is not None:
        partes.append(f"Prêmio: {_cel(prop.premio_centavos)}")
    if prop.iof_centavos is not None:
        partes.append(f"IOF: {_cel(prop.iof_centavos)}")
    if prop.total_recorrente_centavos is not None:
        partes.append(f"Total recorrente: {_cel(prop.total_recorrente_centavos)}")
    return " · ".join(partes)


def _render_cabecalho_propostas_pagina(
    propostas: list[PropostaApresentacao],
    op_ids: list[str],
) -> str:
    linhas = []
    for op_id in op_ids:
        prop = next((p for p in propostas if p.opcao_id == op_id), None)
        if prop:
            linhas.append(f"<p class='proposta-meta'>{_meta_proposta(prop)}</p>")
    return "".join(linhas)


def _paginas_ou_sintese(secao: SecaoRegimeApresentacao) -> list:
    if secao.paginas_faixas:
        return secao.paginas_faixas
    ids = [p.opcao_id for p in secao.propostas]
    if not ids:
        return []
    from newport_app.models.presentation import PaginaFaixasApresentacao

    return [PaginaFaixasApresentacao(indice=0, propostas_ids=ids)]


def _mapa_rotulos_propostas(model: PresentationViewModel) -> dict[str, str]:
    """Resolve nomes comerciais; fallback numerado — nunca expõe id interno."""
    rotulos: dict[str, str] = {}
    for indice, op_id in enumerate(model.propostas_selecionadas, start=1):
        nome: str | None = None
        for secao in model.secoes_regime:
            prop = next((p for p in secao.propostas if p.opcao_id == op_id), None)
            if prop and (prop.plano_nome or "").strip():
                nome = prop.plano_nome.strip()
                break
        rotulos[op_id] = nome or f"Proposta {indice}"
    return rotulos


def _rotulo_proposta(
    op_id: str,
    propostas: list[PropostaApresentacao],
    rotulos: dict[str, str],
) -> str:
    prop = next((p for p in propostas if p.opcao_id == op_id), None)
    if prop and (prop.plano_nome or "").strip():
        return prop.plano_nome.strip()
    return rotulos.get(op_id, "Proposta")


def _th_proposta(op_id: str, propostas: list[PropostaApresentacao], rotulos: dict[str, str], *, colspan: int | None = None) -> str:
    prop = next((p for p in propostas if p.opcao_id == op_id), None)
    nome = _rotulo_proposta(op_id, propostas, rotulos)
    operadora = ((prop.operadora if prop else "") or "").strip()
    attrs = f" colspan='{colspan}'" if colspan and colspan > 1 else ""
    # Operadora via data-l + CSS ::before para o texto da célula permanecer só o nome
    # (testes de gabarito fazem match exato no cabeçalho).
    od = (
        f"<span class='od' data-l='{html.escape(operadora, quote=True)}'></span>"
        if operadora
        else ""
    )
    return f"<th{attrs}><span class='op'>{html.escape(nome)}</span>{od}</th>"


def _planos_reais(secao: SecaoRegimeApresentacao) -> list[PlanoAtualApresentacao]:
    return [p for p in secao.planos_atuais if p.subgrupo_id != "vidas-incluidas"]


def _vidas_plano(plano: PlanoAtualApresentacao) -> int:
    return sum(fx.qtd_total for fx in plano.faixas)


def _tem_copart_percentual(model: PresentationViewModel) -> bool:
    return any(p.regime_tipo == "percentual" for s in model.secoes_regime for p in s.propostas)


def _subtotal_proposta_plano(plano: PlanoAtualApresentacao, op_id: str) -> int | None:
    vals = [
        col.subtotal_centavos
        for fx in plano.faixas
        for col in fx.propostas
        if col.opcao_id == op_id and col.subtotal_centavos is not None
    ]
    return sum(vals) if vals else None


def _cel_subtotal_plano(plano: PlanoAtualApresentacao, op_id: str) -> str:
    valor = _subtotal_proposta_plano(plano, op_id)
    if valor is not None:
        return _cel(valor)
    tem_coluna = any(col.opcao_id == op_id for fx in plano.faixas for col in fx.propostas)
    if tem_coluna:
        return "Sem valor neste plano"
    return "Proposta de outro regime"


def _render_linha_faixa(
    fx: FaixaApresentacao,
    op_ids: list[str],
    *,
    seguro_novo: bool = False,
    reajuste_percentual: str | None = None,
) -> str:
    partes = [
        f"<tr><td>{html.escape(fx.rotulo)}</td>",
        f"<td>{fx.qtd_titulares}</td><td>{fx.qtd_dependentes}</td><td>{fx.qtd_total}</td>",
    ]
    if not seguro_novo:
        reaj = fx.atual_reajustado_total_centavos
        if fx.atual_reajustado_unitario_centavos is not None and fx.qtd_total > 0:
            cel_reaj = (
                f"{_cel(fx.atual_reajustado_unitario_centavos)}"
                f"<span class='uni'>total {_cel(reaj)}</span>"
            )
        else:
            cel_reaj = _cel(reaj)
        if reajuste_percentual:
            cel_reaj = f"{cel_reaj}<span class='ajuste'>{html.escape(reajuste_percentual)}</span>"
        partes.append(f"<td class='atual'>{cel_reaj}</td>")

    for op_id in op_ids:
        col = next((c for c in fx.propostas if c.opcao_id == op_id), None)
        if col is None or col.quantidade == 0:
            partes.append("<td></td><td></td><td></td>")
            continue
        unit = _cel(col.valor_unitario_centavos)
        partes.append(
            f"<td>{unit}</td><td>{col.quantidade}</td><td>{_cel(col.subtotal_centavos)}</td>"
        )
    obs = (fx.observacao_valor or "").strip()
    partes.append(f"<td>{html.escape(obs) if obs else ''}</td></tr>")
    return "".join(partes)


def _render_tabela_faixas(
    plano: PlanoAtualApresentacao,
    propostas: list[PropostaApresentacao],
    op_ids: list[str],
    rotulos: dict[str, str],
    *,
    seguro_novo: bool = False,
) -> str:
    if seguro_novo:
        partes = ["<h3>Distribuição por faixa etária</h3>"]
    else:
        partes = [
            f"<h3>Plano atual — {html.escape(plano.operadora)} · {html.escape(plano.plano_nome)}</h3>",
        ]
        meta = []
        if plano.acomodacao:
            meta.append(f"Acomodação: {html.escape(plano.acomodacao)}")
        if plano.copart_descricao:
            meta.append(f"Coparticipação: {html.escape(plano.copart_descricao)}")
        if meta:
            partes.append(f"<p class='plano-meta'>{' · '.join(meta)}</p>")

    partes.append("<div class='rolo'><table><thead><tr>")
    partes.append("<th>Faixa</th><th>Tit.</th><th>Dep.</th><th>Vidas</th>")
    if not seguro_novo:
        partes.append(
            "<th class='atual'><span class='op'>Contrato atual</span>"
            "<span class='od' data-l='REAJUSTADO'></span></th>"
        )
    for op_id in op_ids:
        partes.append(_th_proposta(op_id, propostas, rotulos, colspan=3))
    partes.append("<th>Obs.</th></tr></thead><tbody>")

    for fx in plano.faixas:
        partes.append(
            _render_linha_faixa(
                fx,
                op_ids,
                seguro_novo=seguro_novo,
                reajuste_percentual=plano.reajuste_percentual_exibicao,
            )
        )

    colspan_base = 4
    partes.append(f"</tbody><tfoot><tr><td colspan='{colspan_base}'>Totais</td>")
    if not seguro_novo:
        partes.append(
            f"<td class='atual'>{_cel_contrato_atual(plano.subtotal_reajustado_centavos, plano.reajuste_percentual_exibicao)}</td>"
        )
    for op_id in op_ids:
        subtotal = sum(
            col.subtotal_centavos or 0
            for fx in plano.faixas
            for col in fx.propostas
            if col.opcao_id == op_id
        )
        partes.append(f"<td colspan='3'>{_cel(subtotal if subtotal else None)}</td>")
    partes.append("<td></td></tr></tfoot></table></div>")
    return "".join(partes)


def _render_totais_secao(
    secao: SecaoRegimeApresentacao,
    op_ids: list[str],
    rotulos: dict[str, str],
    *,
    seguro_novo: bool = False,
) -> str:
    titulo = "Comparativo entre propostas" if seguro_novo else "Totais mensais"
    partes = [f"<div class='totais-secao'><h4>{titulo}</h4><div class='rolo'><table><thead><tr>"]
    partes.append("<th></th>")
    if not seguro_novo:
        partes.append("<th class='atual'><span class='op'>Contrato atual</span></th>")
    for op_id in op_ids:
        partes.append(_th_proposta(op_id, secao.propostas, rotulos))
    partes.append("</tr></thead><tbody>")

    partes.append("<tr><td>Total mensal</td>")
    if not seguro_novo:
        partes.append(f"<td class='atual'>{_cel(secao.totais.atual_centavos)}</td>")
    for op_id in op_ids:
        partes.append(f"<td>{_cel(secao.totais.propostas.get(op_id))}</td>")
    partes.append("</tr>")

    if not seguro_novo:
        partes.append("<tr><td>Diferença mensal</td><td class='atual'>referência</td>")
        for op_id in op_ids:
            partes.append(f"<td>{_cel_diff(secao.totais.diff_mensal.get(op_id))}</td>")
        partes.append("</tr><tr><td>Diferença anual</td><td class='atual'></td>")
        for op_id in op_ids:
            partes.append(f"<td>{_cel_diff(secao.totais.diff_anual.get(op_id))}</td>")
        partes.append("</tr>")
    elif len(op_ids) >= 2:
        totais = [secao.totais.propostas.get(op_id) for op_id in op_ids]
        validos = [t for t in totais if t is not None]
        if validos:
            menor = min(validos)
            partes.append("<tr><td>Diferença vs menor proposta</td>")
            for total in totais:
                if total is None:
                    partes.append("<td></td>")
                else:
                    partes.append(f"<td>{_cel_diff(total - menor)}</td>")
            partes.append("</tr>")

    partes.append("</tbody></table></div></div>")
    return "".join(partes)


def _cel_indicador_linha(cel, *, como_diff: bool) -> str:
    """Renderiza célula de indicador; ausência = «—» (mesma convenção da matriz)."""
    if cel is None:
        return ""
    if cel.referencia and (cel.centavos is None or cel.centavos == 0):
        return html.escape(cel.texto or "referência")
    if cel.ausente:
        return html.escape(cel.texto if cel.texto is not None else "—")
    if cel.texto is not None and cel.centavos is None and cel.bps is None:
        return html.escape(cel.texto)
    from newport_app.presentation.reajuste import formatar_rotulo_reajuste_bps

    if cel.centavos is not None:
        base = _cel_diff_ou_referencia(cel.centavos) if como_diff else _cel(cel.centavos)
        if cel.bps is not None:
            pct = html.escape(formatar_rotulo_reajuste_bps(cel.bps))
            return f"{base}<span class='ajuste'> ({pct})</span>"
        return base
    if cel.bps is not None:
        return html.escape(formatar_rotulo_reajuste_bps(cel.bps))
    return ""


def _render_linha_indicador(
    linha,
    op_ids: list[str],
    *,
    seguro_novo: bool,
) -> str:
    como_diff = linha.rotulo.startswith("Diferença") or linha.rotulo.startswith(
        "Variação"
    )
    cls = " class='destaque'" if linha.destaque else ""
    partes = [f"<tr{cls}><td>{html.escape(linha.rotulo)}</td>"]
    if not seguro_novo:
        if linha.atual is None:
            partes.append("<td class='atual'></td>")
        elif linha.atual.referencia and linha.atual.centavos is None:
            partes.append(
                f"<td class='atual'>{html.escape(linha.atual.texto or 'referência')}</td>"
            )
        else:
            partes.append(
                f"<td class='atual'>{_cel_indicador_linha(linha.atual, como_diff=como_diff)}</td>"
            )
    for op_id in op_ids:
        cel = linha.propostas.get(op_id)
        partes.append(f"<td>{_cel_indicador_linha(cel, como_diff=como_diff)}</td>")
    partes.append("</tr>")
    return "".join(partes)


def _render_resumo(
    model: PresentationViewModel,
    secao: SecaoRegimeApresentacao,
    rotulos: dict[str, str],
    op_ids: list[str],
    *,
    seguro_novo: bool,
) -> str:
    planos = _planos_reais(secao)
    indicadores = list(secao.indicadores_resumo)
    if not indicadores:
        # Fallback: monta a partir do VM se a seção veio sem indicadores.
        from newport_app.presentation.indicadores_resumo import montar_indicadores_resumo

        indicadores = montar_indicadores_resumo(model, secao, op_ids)

    partes = [
        "<section class='secao-regime'>",
        f"<h2>Resumo executivo — {html.escape(secao.regime_rotulo)}</h2>",
    ]
    if len(model.secoes_regime) > 1 or secao.regime_rotulo:
        n_prop = len(op_ids)
        partes.append(
            f"<div class='regime'><b>{html.escape(secao.regime_rotulo)}</b><i></i>"
            f"<em>{n_prop} proposta{'s' if n_prop != 1 else ''}</em></div>"
        )

    partes.append("<div class='rolo'><table><thead><tr><th>Indicador</th>")
    if not seguro_novo:
        od = f"{model.qtd_planos_vigentes} PLANOS" if model.qtd_planos_vigentes else ""
        partes.append(
            "<th class='atual'><span class='op'>Contrato atual</span>"
            + (
                f"<span class='od' data-l='{html.escape(od, quote=True)}'></span>"
                if od
                else ""
            )
            + "</th>"
        )
    for op_id in op_ids:
        partes.append(_th_proposta(op_id, secao.propostas, rotulos))
    partes.append("</tr></thead><tbody>")

    cabecalho = [i for i in indicadores if i.grupo == "cabecalho"]
    rodape = [i for i in indicadores if i.grupo == "rodape"]

    for lin in cabecalho:
        partes.append(
            _render_linha_indicador(lin, op_ids, seguro_novo=seguro_novo)
        )

    if not seguro_novo:
        for plano in planos:
            vidas = _vidas_plano(plano)
            vidas_attr = f" data-vidas='{vidas}'" if vidas > 0 else ""
            partes.append(
                f"<tr><td{vidas_attr}>{html.escape(plano.plano_nome)}</td>"
            )
            partes.append(
                f"<td class='atual'>{_cel_contrato_atual(plano.subtotal_reajustado_centavos, plano.reajuste_percentual_exibicao)}</td>"
            )
            for op_id in op_ids:
                partes.append(f"<td>{_cel_subtotal_plano(plano, op_id)}</td>")
            partes.append("</tr>")
        # Matriz sempre exibe Consolidado quando há plano vigente.
        if planos:
            partes.append("<tr><td><strong>Consolidado</strong></td>")
            reaj_c = sum((p.subtotal_reajustado_centavos or 0) for p in planos) or None
            partes.append(
                f"<td class='atual'><strong>{_cel_contrato_atual(reaj_c, model.reajuste_consolidado_percentual_exibicao)}</strong></td>"
            )
            for op_id in op_ids:
                total = secao.totais.propostas.get(op_id)
                if total is None:
                    total = model.totais_gerais.propostas.get(op_id)
                partes.append(f"<td><strong>{_cel(total)}</strong></td>")
            partes.append("</tr>")

    for lin in rodape:
        partes.append(
            _render_linha_indicador(lin, op_ids, seguro_novo=seguro_novo)
        )

    partes.append("</tbody></table></div></section>")
    return "".join(partes)


def _render_recomendacao(model: PresentationViewModel, rotulos: dict[str, str]) -> str:
    seguro_novo = model.formato == "novo"
    cards: list[str] = []

    if not seguro_novo:
        diffs = [
            (op_id, model.totais_gerais.diff_anual.get(op_id))
            for op_id in model.propostas_selecionadas
            if model.totais_gerais.diff_anual.get(op_id) is not None
        ]
        if diffs:
            melhor_id, melhor_diff = min(diffs, key=lambda x: x[1] if x[1] is not None else 0)
            if melhor_diff is not None and melhor_diff < 0:
                economia = abs(melhor_diff)
                cards.append(
                    "<div class='rc melhor'><span class='rt'>Maior economia</span>"
                    f"<span class='rv'>{_cel(economia)}</span>"
                    f"<span class='rn'>ao ano · {html.escape(rotulos.get(melhor_id, 'Proposta'))}</span></div>"
                )
            # Melhor sem copart (se distinto)
            sem_copart = [
                (op_id, d)
                for op_id, d in diffs
                if d is not None
                and not any(
                    p.opcao_id == op_id and p.regime_tipo == "percentual"
                    for s in model.secoes_regime
                    for p in s.propostas
                )
            ]
            if sem_copart:
                sid, sdiff = min(sem_copart, key=lambda x: x[1] if x[1] is not None else 0)
                if sdiff is not None and sdiff < 0 and sid != (melhor_id if melhor_diff and melhor_diff < 0 else None):
                    cards.append(
                        "<div class='rc'><span class='rt'>Sem coparticipação</span>"
                        f"<span class='rv'>{_cel(abs(sdiff))}</span>"
                        f"<span class='rn'>ao ano · {html.escape(rotulos.get(sid, 'Proposta'))}</span></div>"
                    )
        if model.totais_gerais.atual_centavos is not None:
            base_ano = model.totais_gerais.atual_centavos * 12
            base_rotulo = model.totais_gerais.baseline_rotulo or "contrato atual"
            cards.append(
                "<div class='rc'><span class='rt'>Base atual</span>"
                f"<span class='rv'>{_cel(base_ano)}</span>"
                f"<span class='rn'>ao ano · {html.escape(base_rotulo)}</span></div>"
            )
    else:
        totais = [
            (op_id, model.totais_gerais.propostas.get(op_id))
            for op_id in model.propostas_selecionadas
            if model.totais_gerais.propostas.get(op_id) is not None
        ]
        if totais:
            menor_id, menor_val = min(totais, key=lambda x: x[1] if x[1] is not None else 0)
            if menor_val is not None:
                cards.append(
                    "<div class='rc melhor'><span class='rt'>Menor mensalidade</span>"
                    f"<span class='rv'>{_cel(menor_val)}</span>"
                    f"<span class='rn'>{html.escape(rotulos.get(menor_id, 'Proposta'))}</span></div>"
                )

    if not cards:
        return ""
    return "<div class='recomenda'>" + "".join(cards) + "</div>"


def _nota_copart(model: PresentationViewModel) -> str:
    if not _tem_copart_percentual(model):
        return ""
    return (
        "<p class='nota'><b>Coparticipação.</b> A proposta com coparticipação apresenta "
        "menor mensalidade, mas o beneficiário passa a pagar parte do valor a cada utilização. "
        "A comparação de mensalidade isolada não reflete o custo total.</p>"
    )


def _fatos_capa(model: PresentationViewModel) -> str:
    fatos: list[str] = []
    if model.vidas_calculadas is not None and model.vidas_calculadas > 0:
        fatos.append(
            f"<div class='ft'><b>{model.vidas_calculadas}</b><span>VIDAS</span></div>"
        )
    if model.formato != "novo" and model.qtd_planos_vigentes:
        fatos.append(
            f"<div class='ft'><b>{model.qtd_planos_vigentes}</b><span>PLANOS ATUAIS</span></div>"
        )
    if model.formato != "novo" and model.totais_gerais.atual_centavos is not None:
        fatos.append(
            f"<div class='ft'><b>{_cel(model.totais_gerais.atual_centavos)}</b>"
            "<span>BASE MENSAL REAJUSTADA</span></div>"
        )
    n_prop = len(model.propostas_selecionadas)
    if n_prop > 0:
        fatos.append(f"<div class='ft'><b>{n_prop}</b><span>PROPOSTAS</span></div>")
    if not fatos:
        return ""
    return "<div class='fatos n'>" + "".join(fatos) + "</div>"


def _montar_capa(model: PresentationViewModel) -> str:
    cliente = (model.subtitulo or "").strip()
    titulo = (model.titulo or "").strip()
    if cliente:
        h1 = f"<h1>{html.escape(cliente)}"
        if titulo:
            h1 += f"<em>{html.escape(titulo)}</em>"
        h1 += "</h1>"
    else:
        h1 = f"<h1>{html.escape(titulo)}</h1>" if titulo else ""

    partes = [
        "<header class='capa'>",
        f"<div class='marca'><img class='logo' src='{logo_data_uri()}' alt='Newport'></div>",
        "<p class='eyebrow'>Comparativo de benefícios · Saúde</p>",
        h1,
        f"<p class='lead'>{html.escape(lema_newport())}</p>",
        _fatos_capa(model),
    ]
    if model.formato != "novo" and model.totais_gerais.baseline_rotulo:
        partes.append(
            f"<p class='ref-atual'>Referência atual · {html.escape(model.totais_gerais.baseline_rotulo)}</p>"
        )
    if model.data_apresentacao:
        partes.append(
            f"<p class='revisado'>Revisado em {html.escape(model.data_apresentacao)}</p>"
        )
    partes.append("</header>")
    return "".join(partes)


def _montar_rodape(model: PresentationViewModel) -> str:
    site_url, site_rotulo = site_newport()
    direita: list[str] = []
    if (model.subtitulo or "").strip():
        direita.append(html.escape(model.subtitulo.strip()))
    if (model.titulo or "").strip():
        direita.append(html.escape(model.titulo.strip()))
    if model.data_apresentacao:
        direita.append(f"Revisado em {html.escape(model.data_apresentacao)}")
    direita_html = " · ".join(direita) if direita else ""
    return (
        "<footer class='pe'>"
        f"<div><img class='logo-pe' src='{logo_data_uri()}' alt='Newport'>"
        f"{html.escape(rotulo_consultoria())} · "
        f"<a href='{html.escape(site_url)}'>{html.escape(site_rotulo)}</a></div>"
        f"<div>{direita_html}</div>"
        "</footer>"
    )


def _avisos_topo(model: PresentationViewModel, *, aviso_pii: bool) -> str:
    partes = [
        f"<div class='rascunho'>{html.escape(model.aviso_rascunho_interno)}</div>",
    ]
    if model.avisos_acomodacao:
        partes.append("<div class='aviso-acomodacao'><strong>Atenção — acomodação divergente</strong><ul>")
        for aviso in model.avisos_acomodacao:
            partes.append(f"<li>{html.escape(aviso)}</li>")
        partes.append("</ul></div>")
    if model.avisos_acomodacao_incompleto:
        partes.append(
            "<div class='aviso-acomodacao aviso-acomodacao--info'>"
            "<strong>Acomodação incompleta</strong><ul>"
        )
        for aviso in model.avisos_acomodacao_incompleto:
            partes.append(f"<li>{html.escape(aviso)}</li>")
        partes.append("</ul></div>")
    if aviso_pii:
        partes.append(
            "<div class='aviso-pii'>Este material contém nomes de beneficiários. "
            "Mantenha em armazenamento privado.</div>"
        )
    return "".join(partes)


def _tit_secao(numero: str, linha1: str, linha2: str, lead: str) -> str:
    return (
        f"<div class='tit'><span class='n1'>{html.escape(numero)}</span>"
        f"<h2>{html.escape(linha1)}<span>{html.escape(linha2)}</span></h2>"
        f"<p>{html.escape(lead)}</p></div>"
    )


def _paginas_corpo_visao(model: PresentationViewModel) -> list[list[str]]:
    """Blocos de página da visão (sem capa)."""
    paginas: list[list[str]] = []
    rotulos = _mapa_rotulos_propostas(model)
    seguro_novo = model.formato == "novo"

    if model.modo == "resumo":
        for secao in model.secoes_regime:
            for pagina in _paginas_ou_sintese(secao):
                paginas.append(
                    [
                        _render_resumo(
                            model,
                            secao,
                            rotulos,
                            pagina.propostas_ids,
                            seguro_novo=seguro_novo,
                        )
                    ]
                )
        extra = _render_recomendacao(model, rotulos) + _nota_copart(model)
        if extra:
            if paginas:
                paginas[-1].append(extra)
            else:
                paginas.append([extra])

    if model.modo == "faixas":
        for secao in model.secoes_regime:
            for pagina in _paginas_ou_sintese(secao):
                bloco = [
                    "<section class='secao-regime'>",
                    f"<h2>{html.escape(secao.regime_rotulo)}</h2>",
                    _render_cabecalho_propostas_pagina(secao.propostas, pagina.propostas_ids),
                ]
                for plano in secao.planos_atuais:
                    bloco.append(
                        "<div class='pagina-faixas'>"
                        + _render_tabela_faixas(
                            plano,
                            secao.propostas,
                            pagina.propostas_ids,
                            rotulos,
                            seguro_novo=seguro_novo,
                        )
                        + "</div>"
                    )
                bloco.append(
                    _render_totais_secao(
                        secao,
                        pagina.propostas_ids,
                        rotulos,
                        seguro_novo=seguro_novo,
                    )
                )
                bloco.append("</section>")
                paginas.append(bloco)

    if model.modo == "beneficiario" and model.beneficiarios:
        op_ids = model.propostas_selecionadas
        agregados = all(
            (b.nome or "").startswith("Beneficiário ·") for b in model.beneficiarios
        )
        col_rotulo = "Beneficiário" if agregados else "Nome"
        for i in range(0, len(op_ids), MAX_PROPOSTAS_POR_PAGINA):
            chunk = op_ids[i : i + MAX_PROPOSTAS_POR_PAGINA]
            bloco = ["<section class='secao-regime'><h2>Detalhamento por beneficiário</h2>"]
            bloco.append("<div class='rolo'><table><thead><tr>")
            cab = f"<th>{col_rotulo}</th>"
            if not agregados:
                cab += "<th>Idade</th><th>Faixa</th><th>Parentesco</th>"
            cab += "<th>Plano atual</th>"
            if not seguro_novo:
                cab += (
                    "<th class='atual'><span class='op'>Contrato atual</span>"
                    "<span class='od' data-l='REAJUSTADO'></span></th>"
                )
            bloco.append(cab)
            for op_id in chunk:
                bloco.append(_th_proposta(op_id, [], rotulos))
            bloco.append("</tr></thead><tbody>")
            pct_por_subgrupo: dict[str, str | None] = {}
            for secao in model.secoes_regime:
                for pl in secao.planos_atuais:
                    pct_por_subgrupo[pl.subgrupo_id] = pl.reajuste_percentual_exibicao
            for b in model.beneficiarios:
                pct = pct_por_subgrupo.get(b.subgrupo_id or "")
                linha = f"<tr><td>{html.escape(b.nome)}</td>"
                if not agregados:
                    idade = "" if b.idade is None else str(b.idade)
                    faixa = html.escape(b.faixa_rotulo or "")
                    parentesco = html.escape(b.parentesco or "")
                    linha += f"<td>{idade}</td><td>{faixa}</td><td>{parentesco}</td>"
                linha += f"<td>{html.escape(b.plano_atual or '')}</td>"
                if not seguro_novo:
                    linha += f"<td class='atual'>{_cel_contrato_atual(b.atual_reajustado_centavos, pct)}</td>"
                bloco.append(linha)
                for op_id in chunk:
                    col = next((c for c in b.propostas if c.opcao_id == op_id), None)
                    val = _cel(col.valor_centavos if col else None)
                    diff = _cel_diff(col.diff_centavos if col else None)
                    if diff:
                        bloco.append(f"<td>{val}<span class='uni'>{diff}</span></td>")
                    else:
                        bloco.append(f"<td>{val}</td>")
                bloco.append("</tr>")
            bloco.append("</tbody></table></div></section>")
            paginas.append(bloco)

    if model.modo == "grupo_familiar" and model.grupos_familiares:
        op_ids = model.propostas_selecionadas
        agregados = all(
            (g.rotulo or "").startswith("Grupo familiar ·") for g in model.grupos_familiares
        )
        for i in range(0, len(op_ids), MAX_PROPOSTAS_POR_PAGINA):
            chunk = op_ids[i : i + MAX_PROPOSTAS_POR_PAGINA]
            bloco = [
                "<section class='secao-regime'><h2>Detalhamento por grupo familiar</h2>"
            ]
            pct_por_subgrupo: dict[str, str | None] = {}
            for secao in model.secoes_regime:
                for pl in secao.planos_atuais:
                    pct_por_subgrupo[pl.subgrupo_id] = pl.reajuste_percentual_exibicao
            for g in model.grupos_familiares:
                bloco.append(
                    f"<h3 class='grupo-familiar-titulo'>{html.escape(g.rotulo)}</h3>"
                )
                bloco.append("<div class='rolo'><table><thead><tr>")
                col_rotulo = "Membro" if agregados else "Nome"
                cab = f"<th>{col_rotulo}</th>"
                if not agregados:
                    cab += "<th>Idade</th><th>Faixa</th><th>Vínculo</th>"
                cab += "<th>Plano atual</th>"
                if not seguro_novo:
                    cab += (
                        "<th class='atual'><span class='op'>Contrato atual</span>"
                        "<span class='od' data-l='REAJUSTADO'></span></th>"
                    )
                bloco.append(cab)
                for op_id in chunk:
                    bloco.append(_th_proposta(op_id, [], rotulos))
                bloco.append("</tr></thead><tbody>")
                for b in g.membros:
                    pct = pct_por_subgrupo.get(b.subgrupo_id or "")
                    linha = f"<tr><td>{html.escape(b.nome)}</td>"
                    if not agregados:
                        idade = "" if b.idade is None else str(b.idade)
                        faixa = html.escape(b.faixa_rotulo or "")
                        parentesco = html.escape(b.parentesco or "")
                        linha += f"<td>{idade}</td><td>{faixa}</td><td>{parentesco}</td>"
                    linha += f"<td>{html.escape(b.plano_atual or '')}</td>"
                    if not seguro_novo:
                        linha += (
                            f"<td class='atual'>"
                            f"{_cel_contrato_atual(b.atual_reajustado_centavos, pct)}</td>"
                        )
                    bloco.append(linha)
                    for op_id in chunk:
                        col = next((c for c in b.propostas if c.opcao_id == op_id), None)
                        val = _cel(col.valor_centavos if col else None)
                        diff = _cel_diff(col.diff_centavos if col else None)
                        if diff:
                            bloco.append(f"<td>{val}<span class='uni'>{diff}</span></td>")
                        else:
                            bloco.append(f"<td>{val}</td>")
                    bloco.append("</tr>")
                if g.exibir_subtotal:
                    colspan = 1 + (0 if agregados else 3) + 1 + (0 if seguro_novo else 1)
                    sub = (
                        f"<tr class='total-row'><td colspan='{colspan}'>"
                        f"Subtotal · {html.escape(g.rotulo)}</td>"
                    )
                    if not seguro_novo:
                        sub = (
                            f"<tr class='total-row'><td>"
                            f"Subtotal · {html.escape(g.rotulo)}</td>"
                        )
                        if not agregados:
                            sub += "<td></td><td></td><td></td>"
                        sub += "<td></td>"
                        sub += (
                            f"<td class='atual'>"
                            f"{_cel(g.subtotal_atual_reajustado_centavos)}</td>"
                        )
                    else:
                        sub = (
                            f"<tr class='total-row'><td>"
                            f"Subtotal · {html.escape(g.rotulo)}</td>"
                        )
                        if not agregados:
                            sub += "<td></td><td></td><td></td>"
                        sub += "<td></td>"
                    bloco.append(sub)
                    for op_id in chunk:
                        col = next(
                            (c for c in g.subtotal_propostas if c.opcao_id == op_id),
                            None,
                        )
                        val = _cel(col.valor_centavos if col else None)
                        diff = _cel_diff(col.diff_centavos if col else None)
                        if diff:
                            bloco.append(f"<td>{val}<span class='uni'>{diff}</span></td>")
                        else:
                            bloco.append(f"<td>{val}</td>")
                    bloco.append("</tr>")
                bloco.append("</tbody></table></div>")
            bloco.append("</section>")
            paginas.append(bloco)

    if model.ressalvas:
        res = ["<section class='ressalvas'><h3>Ressalvas comerciais</h3><ul>"]
        for r in model.ressalvas:
            res.append(f"<li>{html.escape(r)}</li>")
        res.append("</ul></section>")
        paginas.append(res)

    return paginas


_CSS = """
:root{
  --grafite:#232932;--grafite-2:#3A3F47;--grafite-3:#5B5B58;
  --ouro:#BF995B;--ouro-cl:#F6F0E6;--ouro-esc:#A68055;
  --ciano:#37B5FF;
  --papel:#FFFFFF;--papel-2:#F7F7F5;--papel-3:#EFEEEA;
  --risco:#DEDCD6;
  --verde:#1E7A5A;--vinho:#A8323C;
  --sans:'Poppins',system-ui,sans-serif;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--papel-2);color:var(--grafite);font-family:var(--sans);
  font-size:14px;font-weight:400;line-height:1.55;-webkit-font-smoothing:antialiased}
.n{font-variant-numeric:tabular-nums;font-feature-settings:"tnum" 1}
.folha{max-width:1180px;margin:0 auto;background:var(--papel);
  box-shadow:0 1px 3px rgba(35,41,50,.07),0 12px 40px rgba(35,41,50,.06)}
.capa{background:var(--grafite);color:#fff;padding:44px 56px 40px;position:relative;overflow:hidden}
.capa .logo{height:92px;width:auto;display:block}
.marca{margin-bottom:38px;position:relative;z-index:2}
.capa .eyebrow{font-size:11px;font-weight:600;letter-spacing:.28em;color:var(--ouro);margin:0 0 12px}
.capa h1{margin:0;font-size:38px;font-weight:800;letter-spacing:-.03em;line-height:1.05}
.capa h1 em{display:block;font-style:normal;font-weight:300;color:#B9BEC6;font-size:24px;margin-top:6px}
.capa .lead{margin:26px 0 0;font-size:13.5px;font-weight:300;color:#C9CDD3;max-width:56ch}
.capa .fatos{display:flex;flex-wrap:wrap;gap:0;margin-top:32px}
.capa .ft{padding-right:38px;margin-right:38px;border-right:1px solid rgba(255,255,255,.14)}
.capa .ft:last-child{border-right:0;margin-right:0;padding-right:0}
.capa .ft b{display:block;font-size:26px;font-weight:700;letter-spacing:-.035em;line-height:1}
.capa .ft span{display:block;font-size:10.5px;font-weight:500;letter-spacing:.16em;color:#8E949D;margin-top:6px}
.capa .ref-atual,.capa .revisado{margin:18px 0 0;font-size:12px;font-weight:400;color:#8E949D}
.rascunho{background:var(--ouro-cl);border-bottom:1px solid rgba(191,153,91,.4);
  padding:11px 56px;font-size:12px;font-weight:500;color:var(--ouro-esc);letter-spacing:.03em}
.aviso-pii{background:#FBEDEE;border-bottom:1px solid #E8B4B8;padding:11px 56px;color:#A8323C;font-size:12.5px}
.aviso-acomodacao{background:#FFF8E1;border-bottom:1px solid #FFE082;padding:11px 56px;color:#6d4c00;font-size:12.5px}
.aviso-acomodacao--info{background:#E3F2FD;border-bottom-color:#90CAF9;color:#0d47a1}
.aviso-acomodacao ul{margin:6px 0 0;padding-left:1.2rem}
.doc-tab-input{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.doc-controles{display:flex;align-items:center;gap:0;flex-wrap:wrap;padding:0 56px;background:var(--papel);
  border-bottom:1px solid var(--risco);position:sticky;top:0;z-index:20}
.doc-abas{display:flex;flex-wrap:wrap;gap:0}
.doc-aba{padding:17px 0;margin-right:34px;font-size:12px;font-weight:600;letter-spacing:.14em;
  text-transform:uppercase;color:var(--grafite-3);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px}
.doc-aba:hover{color:var(--grafite)}
.doc-btn-todas,.doc-btn-voltar{margin-left:auto;margin-right:0;border:1px solid var(--risco);border-radius:2px;
  padding:8px 15px;font-size:11px;letter-spacing:.12em;align-self:center;cursor:pointer;font-weight:600}
.doc-btn-todas:hover,.doc-btn-voltar:hover{border-color:var(--ouro);color:var(--ouro-esc);background:var(--ouro-cl)}
.doc-btn-voltar{display:none}
#tab-resumo:checked ~ .doc-controles label[for=tab-resumo],
#tab-faixas:checked ~ .doc-controles label[for=tab-faixas],
#tab-benef:checked ~ .doc-controles label[for=tab-benef]{color:var(--grafite);border-bottom-color:var(--ouro)}
#tab-todas:checked ~ .doc-controles .doc-btn-todas{background:var(--grafite);border-color:var(--grafite);color:#fff}
#tab-todas:checked ~ .doc-controles .doc-btn-todas{display:none}
#tab-todas:checked ~ .doc-controles .doc-btn-voltar{display:inline-block}
#tab-todas:checked ~ .doc-controles .doc-abas{opacity:.45;pointer-events:none}
.visao { display: none; }
#tab-resumo:checked ~ .doc-corpo .visao-resumo,
#tab-faixas:checked ~ .doc-corpo .visao-faixas,
#tab-benef:checked ~ .doc-corpo .visao-benef{display:block}
#tab-todas:checked ~ .doc-corpo .visao { display: block !important; }
.corpo,.doc-corpo{padding:0 56px 64px}
.visao-titulo{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.tit{padding:44px 0 22px}
.tit .n1{display:block;font-size:11px;font-weight:600;letter-spacing:.26em;color:var(--ouro);margin-bottom:9px}
.tit h2{margin:0;font-size:29px;font-weight:800;letter-spacing:-.035em;line-height:1.05;text-transform:uppercase}
.tit h2 span{display:block;font-weight:300;color:var(--grafite-3);text-transform:none}
.tit p{margin:12px 0 0;font-size:13.5px;font-weight:300;color:var(--grafite-2);max-width:74ch}
.regime{display:flex;align-items:center;gap:14px;margin:34px 0 16px}
.regime b{font-size:11px;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--grafite);white-space:nowrap}
.regime i{flex:1;height:1px;background:var(--risco)}
.regime em{font-style:normal;font-size:11.5px;font-weight:400;color:var(--grafite-3);white-space:nowrap}
.secao-regime h2{font-size:1.05rem;margin:28px 0 12px;color:var(--grafite)}
.secao-regime h3{font-size:1rem;margin:16px 0 8px}
.plano-meta,.proposta-meta{font-size:.85rem;color:var(--grafite-3);margin:6px 0}
.rolo{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0 20px}
th,td{padding:13px 14px;text-align:right;white-space:nowrap;vertical-align:top}
th:first-child,td:first-child{text-align:left;white-space:normal;padding-left:0}
thead th{background:var(--grafite);color:#fff;font-size:10.5px;font-weight:600;letter-spacing:.1em;
  text-transform:uppercase;padding-top:12px;padding-bottom:12px;vertical-align:bottom}
thead th .op{display:block;font-size:12.5px;font-weight:600;letter-spacing:-.01em;text-transform:none;margin-bottom:3px}
thead th .od{display:block;font-size:10px;font-weight:400;letter-spacing:.1em;color:#9AA0A8}
thead th .od::before{content:attr(data-l)}
th.atual{background:var(--ouro)}
th.atual .od{color:#F2E7D5}
td.atual{background:var(--ouro-cl)}
tbody td{border-bottom:1px solid var(--risco)}
tr.plano td:first-child{font-weight:600}
tbody tr td:first-child[data-vidas]::after{
  content:attr(data-vidas) " vidas";display:block;font-size:11.5px;font-weight:400;
  color:var(--grafite-3);margin-top:2px;text-transform:none;letter-spacing:0}
tbody tr[data-row=consolidado] td{border-top:2px solid var(--grafite);font-weight:700;font-size:14.5px;background:var(--papel-2)}
tbody tr[data-row=consolidado] td.atual{background:#F1E7D6}
tfoot tr td{border-top:2px solid var(--grafite);font-weight:700;font-size:14.5px;background:var(--papel-2)}
tfoot tr td.atual{background:#F1E7D6}
.ajuste{display:inline;font-size:11px;font-weight:600;color:var(--ouro-esc);margin-left:5px}
.neg{color:var(--verde)}.pos{color:var(--vinho)}
.uni{display:block;font-size:11px;font-weight:400;color:var(--grafite-3);margin-top:2px}
#tab-resumo:focus-visible ~ .doc-controles label[for="tab-resumo"],
#tab-faixas:focus-visible ~ .doc-controles label[for="tab-faixas"],
#tab-benef:focus-visible ~ .doc-controles label[for="tab-benef"],
#tab-todas:focus-visible ~ .doc-controles label[for="tab-todas"],
#tab-resumo:focus-visible ~ .doc-controles label.doc-btn-voltar{
  outline:3px solid #93c5fd;outline-offset:2px}
.recomenda{display:flex;gap:0;flex-wrap:wrap;margin:30px 0 0;border:1px solid var(--risco)}
.rc{flex:1;min-width:190px;padding:20px 22px;border-right:1px solid var(--risco)}
.rc:last-child{border-right:0}
.rc.melhor{background:var(--grafite);color:#fff}
.rc .rt{display:block;font-size:10px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--grafite-3);margin-bottom:8px}
.rc.melhor .rt{color:var(--ouro)}
.rc .rv{display:block;font-size:23px;font-weight:700;letter-spacing:-.035em;line-height:1}
.rc .rn{display:block;font-size:12px;font-weight:400;color:var(--grafite-3);margin-top:6px}
.rc.melhor .rn{color:#B9BEC6}
.nota{margin:34px 0 0;padding:16px 20px;background:var(--papel-2);border-left:2px solid var(--ouro);
  font-size:12.5px;font-weight:300;color:var(--grafite-2)}
.nota b{font-weight:600;color:var(--grafite)}
.ressalvas{margin-top:24px;font-size:13px;color:var(--grafite-2)}
.pe{background:var(--grafite);color:#8E949D;padding:30px 56px;display:flex;justify-content:space-between;
  gap:20px;flex-wrap:wrap;font-size:11.5px;font-weight:300}
.pe .logo-pe{height:40px;width:auto;display:block;margin-bottom:8px}
.pe a{color:var(--ciano);text-decoration:none}
@media(max-width:720px){
  .capa,.doc-controles,.corpo,.doc-corpo,.rascunho,.aviso-pii,.aviso-acomodacao,.pe{padding-left:22px;padding-right:22px}
}
@media print{
  body{background:#fff}
  .folha{box-shadow:none;max-width:none}
  .doc-controles,.doc-tab-input{display:none !important}
  .rolo{overflow:visible}
  thead{display:table-header-group}
  .tit,.secao-regime{page-break-after:avoid}
  table{page-break-inside:avoid}
}
"""


def _documento(
    model: PresentationViewModel,
    *,
    aviso_pii: bool,
    corpo: str,
    com_abas: bool,
) -> str:
    titulo_doc = model.subtitulo or model.titulo
    head = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{html.escape(titulo_doc)}</title>",
        f"<style>{poppins_font_face_css()}{_CSS}</style></head><body><div class='folha'>",
        _montar_capa(model),
        _avisos_topo(model, aviso_pii=aviso_pii),
    ]
    return "".join(head) + corpo + _montar_rodape(model) + "</div></body></html>"


def render_html(model: PresentationViewModel) -> str:
    aviso_pii = False
    if model.modo == "beneficiario":
        aviso_pii = not all(
            (b.nome or "").startswith("Beneficiário ·") for b in model.beneficiarios
        )
    elif model.modo == "grupo_familiar":
        aviso_pii = not all(
            (g.rotulo or "").startswith("Grupo familiar ·") for g in model.grupos_familiares
        )
    blocos = ["".join(p) for p in _paginas_corpo_visao(model)]
    corpo = "<div class='corpo'>" + "".join(blocos) + "</div>"
    return _documento(model, aviso_pii=aviso_pii, corpo=corpo, com_abas=False)


def render_html_completo(
    vm_resumo: PresentationViewModel,
    vm_faixas: PresentationViewModel,
    vm_grupos: PresentationViewModel,
) -> str:
    """Documento cliente com três visões — abas em CSS puro (radios)."""
    rotulos = _mapa_rotulos_propostas(vm_resumo)
    seguro_novo = vm_resumo.formato == "novo"
    lead_resumo = (
        "As propostas são comparadas entre si."
        if seguro_novo
        else "O contrato atual está apresentado com o reajuste já aplicado. As propostas são comparadas contra esse valor."
    )
    corpo_resumo = (
        _tit_secao("01", "Comparativo", "Financeiro", lead_resumo)
        + "".join("".join(p) for p in _paginas_corpo_visao(vm_resumo))
    )
    corpo_faixas = (
        _tit_secao(
            "02",
            "Distribuição",
            "Por faixa etária",
            "Valores por faixa da ANS. Faixas sem vidas não são exibidas.",
        )
        + "".join("".join(p) for p in _paginas_corpo_visao(vm_faixas))
    )
    # Aceita VM legado (beneficiario) ou novo (grupo_familiar).
    if vm_grupos.modo == "beneficiario":
        titulo_detalhe = "Por beneficiário"
        lead_detalhe = (
            "Uma linha por vida, identificada pela faixa etária e pelo plano vigente. "
            "Nomes não são exibidos neste material."
        )
        aria_detalhe = "Por beneficiário"
    else:
        titulo_detalhe = "Por grupo familiar"
        lead_detalhe = (
            "Cada titular forma um grupo; dependentes ficam sob o titular. "
            "Subtotal só quando o grupo tem mais de uma pessoa. Nomes não são exibidos neste material."
        )
        aria_detalhe = "Por grupo familiar"
    corpo_grupos = (
        _tit_secao("03", "Detalhamento", titulo_detalhe, lead_detalhe)
        + "".join("".join(p) for p in _paginas_corpo_visao(vm_grupos))
    )
    del rotulos

    corpo = "".join(
        [
            '<input type="radio" name="doc-visao" id="tab-resumo" class="doc-tab-input" checked '
            'aria-label="Resumo executivo">',
            '<input type="radio" name="doc-visao" id="tab-faixas" class="doc-tab-input" '
            'aria-label="Faixas etárias">',
            '<input type="radio" name="doc-visao" id="tab-benef" class="doc-tab-input" '
            f'aria-label="{aria_detalhe}">',
            '<input type="radio" name="doc-visao" id="tab-todas" class="doc-tab-input" '
            'aria-label="Ver as três visões">',
            '<nav class="doc-controles no-print" aria-label="Visões do documento">',
            '<div class="doc-abas" role="tablist" aria-label="Visões">',
            '<label class="doc-aba" for="tab-resumo" role="tab" aria-controls="visao-resumo">'
            "Resumo executivo</label>",
            '<label class="doc-aba" for="tab-faixas" role="tab" aria-controls="visao-faixas">'
            "Faixas etárias</label>",
            '<label class="doc-aba" for="tab-benef" role="tab" aria-controls="visao-benef">'
            f"{titulo_detalhe}</label>",
            "</div>",
            '<label class="doc-btn-todas" for="tab-todas">Ver as três visões</label>',
            '<label class="doc-btn-voltar" for="tab-resumo">Voltar às abas</label>',
            "</nav>",
            '<div class="doc-corpo">',
            '<section class="visao visao-resumo" id="visao-resumo" role="tabpanel" '
            'aria-labelledby="tit-resumo">',
            '<h2 class="visao-titulo" id="tit-resumo">Resumo executivo</h2>',
            corpo_resumo,
            "</section>",
            '<section class="visao visao-faixas" id="visao-faixas" role="tabpanel" '
            'aria-labelledby="tit-faixas">',
            '<h2 class="visao-titulo" id="tit-faixas">Faixas etárias</h2>',
            corpo_faixas,
            "</section>",
            '<section class="visao visao-benef" id="visao-benef" role="tabpanel" '
            'aria-labelledby="tit-benef">',
            f'<h2 class="visao-titulo" id="tit-benef">{titulo_detalhe}</h2>',
            corpo_grupos,
            "</section>",
            "</div>",
        ]
    )
    return _documento(vm_resumo, aviso_pii=False, corpo=corpo, com_abas=True)
