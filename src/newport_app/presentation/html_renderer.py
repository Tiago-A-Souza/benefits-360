"""Renderer HTML autocontido — ETAPA 2.8.1 (sem metadados técnicos no material do cliente)."""

from __future__ import annotations

import html
import re

from newport_app.models.presentation import (
    FaixaApresentacao,
    PlanoAtualApresentacao,
    PresentationViewModel,
    PropostaApresentacao,
    SecaoRegimeApresentacao,
)
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA
from newport_app.presentation.formatacao import formatar_data_br, formatar_reais

RENDERER_VERSAO = "html@2.8.1"
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _cel(valor: int | None) -> str:
    return html.escape(formatar_reais(valor))


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
        if plano.acomodacao or plano.copart_descricao:
            meta = []
            if plano.acomodacao:
                meta.append(f"Acomodação: {html.escape(plano.acomodacao)}")
            if plano.copart_descricao:
                meta.append(f"Coparticipação: {html.escape(plano.copart_descricao)}")
            partes.append(f"<p class='plano-meta'>{' · '.join(meta)}</p>")

    partes.append("<table><thead><tr>")
    partes.append("<th>Faixa</th><th>Tit.</th><th>Dep.</th><th>Vidas</th>")
    if not seguro_novo:
        partes.append("<th>Atual vigente</th><th>Atual reajustado</th>")
    for op_id in op_ids:
        rotulo = _rotulo_proposta(op_id, propostas, rotulos)
        partes.append(
            f"<th colspan='3'>{html.escape(rotulo)}<br><small>Unit. · Qtd · Subtotal</small></th>"
        )
    partes.append("<th>Obs.</th></tr></thead><tbody>")

    for fx in plano.faixas:
        partes.append(_render_linha_faixa(fx, op_ids, seguro_novo=seguro_novo))
    partes.append("</tbody>")

    colspan_base = 4
    partes.append(f"<tfoot><tr><td colspan='{colspan_base}'><strong>Totais</strong></td>")
    if not seguro_novo:
        partes.append(f"<td>{_cel(plano.subtotal_vigente_centavos)}</td>")
        partes.append(f"<td>{_cel(plano.subtotal_reajustado_centavos)}</td>")
    for op_id in op_ids:
        subtotal = sum(
            col.subtotal_centavos or 0
            for fx in plano.faixas
            for col in fx.propostas
            if col.opcao_id == op_id
        )
        partes.append(f"<td colspan='3'>{_cel(subtotal if subtotal else None)}</td>")
    partes.append("<td></td></tr></tfoot></table>")
    return "".join(partes)


def _render_linha_faixa(
    fx: FaixaApresentacao,
    op_ids: list[str],
    *,
    seguro_novo: bool = False,
) -> str:
    partes = [
        f"<tr><td>{html.escape(fx.rotulo)}</td>",
        f"<td>{fx.qtd_titulares}</td><td>{fx.qtd_dependentes}</td><td>{fx.qtd_total}</td>",
    ]
    if not seguro_novo:
        vigente = fx.atual_vigente_total_centavos
        if fx.atual_vigente_unitario_centavos is not None and fx.qtd_total > 0:
            cel_vig = (
                f"{_cel(fx.atual_vigente_unitario_centavos)}"
                f"<br><small>total {_cel(vigente)}</small>"
            )
        else:
            cel_vig = _cel(vigente)

        reaj = fx.atual_reajustado_total_centavos
        if fx.atual_reajustado_unitario_centavos is not None and fx.qtd_total > 0:
            cel_reaj = (
                f"{_cel(fx.atual_reajustado_unitario_centavos)}"
                f"<br><small>total {_cel(reaj)}</small>"
            )
        else:
            cel_reaj = _cel(reaj)
        partes.append(f"<td>{cel_vig}</td><td>{cel_reaj}</td>")

    for op_id in op_ids:
        col = next((c for c in fx.propostas if c.opcao_id == op_id), None)
        if col is None or col.quantidade == 0:
            partes.append("<td>—</td><td>0</td><td>—</td>")
            continue
        unit = _cel(col.valor_unitario_centavos) if col.valor_unitario_centavos else "—"
        partes.append(
            f"<td>{unit}</td><td>{col.quantidade}</td><td>{_cel(col.subtotal_centavos)}</td>"
        )
    partes.append(f"<td>{html.escape(fx.observacao_valor or '')}</td></tr>")
    return "".join(partes)


def _render_totais_secao(
    secao: SecaoRegimeApresentacao,
    op_ids: list[str],
    rotulos: dict[str, str],
    *,
    seguro_novo: bool = False,
) -> str:
    titulo = "Comparativo entre propostas" if seguro_novo else "Totais mensais"
    partes = [f"<div class='totais-secao'><h4>{titulo}</h4><table><thead><tr>"]
    partes.append("<th></th>")
    if not seguro_novo:
        partes.append("<th>Plano atual</th>")
    for op_id in op_ids:
        rotulo = _rotulo_proposta(op_id, secao.propostas, rotulos)
        partes.append(f"<th>{html.escape(rotulo)}</th>")
    partes.append("</tr></thead><tbody>")

    partes.append("<tr><td>Total mensal</td>")
    if not seguro_novo:
        partes.append(f"<td>{_cel(secao.totais.atual_centavos)}</td>")
    for op_id in op_ids:
        partes.append(f"<td>{_cel(secao.totais.propostas.get(op_id))}</td>")
    partes.append("</tr>")

    if not seguro_novo:
        partes.append("<tr><td>Diferença mensal</td><td>—</td>")
        for op_id in op_ids:
            partes.append(f"<td>{_cel(secao.totais.diff_mensal.get(op_id))}</td>")
        partes.append("</tr><tr><td>Diferença anual</td><td>—</td>")
        for op_id in op_ids:
            partes.append(f"<td>{_cel(secao.totais.diff_anual.get(op_id))}</td>")
        partes.append("</tr>")
    elif len(op_ids) >= 2:
        totais = [secao.totais.propostas.get(op_id) for op_id in op_ids]
        validos = [t for t in totais if t is not None]
        if validos:
            menor = min(validos)
            partes.append("<tr><td>Diferença vs menor proposta</td>")
            for total in totais:
                if total is None:
                    partes.append("<td>—</td>")
                else:
                    partes.append(f"<td>{_cel(total - menor)}</td>")
            partes.append("</tr>")

    partes.append("</tbody></table></div>")
    return "".join(partes)


def _planos_unicos(model: PresentationViewModel) -> list[PlanoAtualApresentacao]:
    vistos: dict[str, PlanoAtualApresentacao] = {}
    for secao in model.secoes_regime:
        for plano in secao.planos_atuais:
            vistos.setdefault(plano.subgrupo_id, plano)
    return list(vistos.values())


def _subtotal_proposta_plano(plano: PlanoAtualApresentacao, op_id: str) -> int | None:
    soma = sum(
        col.subtotal_centavos or 0
        for fx in plano.faixas
        for col in fx.propostas
        if col.opcao_id == op_id
    )
    return soma if soma else None


def _render_resumo(
    model: PresentationViewModel,
    rotulos: dict[str, str],
    op_ids: list[str],
    *,
    seguro_novo: bool,
) -> str:
    planos = [p for p in _planos_unicos(model) if p.subgrupo_id != "vidas-incluidas"]
    partes = [
        "<section class='secao-regime'>",
        "<h2>Resumo executivo</h2>",
        "<table><thead><tr><th>Indicador</th>",
    ]
    if not seguro_novo:
        partes.append("<th>Contrato atual</th>")
    for op_id in op_ids:
        partes.append(f"<th>{html.escape(rotulos.get(op_id, 'Proposta'))}</th>")
    partes.append("</tr></thead><tbody>")

    if not seguro_novo:
        for plano in planos:
            partes.append(f"<tr><td>{html.escape(plano.plano_nome)}</td>")
            vigente = _cel(plano.subtotal_vigente_centavos)
            reaj = _cel(plano.subtotal_reajustado_centavos)
            partes.append(f"<td>{vigente} vigente<br><small>{reaj} reajustado</small></td>")
            for op_id in op_ids:
                partes.append(f"<td>{_cel(_subtotal_proposta_plano(plano, op_id))}</td>")
            partes.append("</tr>")
        if planos:
            partes.append("<tr><td>Consolidado</td>")
            tg = model.totais_gerais
            vigente_c = sum((p.subtotal_vigente_centavos or 0) for p in planos) or None
            reaj_c = sum((p.subtotal_reajustado_centavos or 0) for p in planos) or None
            partes.append(f"<td>{_cel(vigente_c)} vigente<br><small>{_cel(reaj_c)} reajustado</small></td>")
            for op_id in op_ids:
                partes.append(f"<td>{_cel(tg.propostas.get(op_id))}</td>")
            partes.append("</tr>")

    partes.append(
        "<tr><td>"
        + ("Diferença vs menor (mês)" if seguro_novo else "Diferença mensal")
        + "</td>"
    )
    if not seguro_novo:
        partes.append("<td>—</td>")
    totais_todas = [
        model.totais_gerais.propostas.get(i) for i in model.propostas_selecionadas
    ]
    validos_todas = [t for t in totais_todas if t is not None]
    menor_global = min(validos_todas) if validos_todas else None
    for op_id in op_ids:
        if seguro_novo:
            total = model.totais_gerais.propostas.get(op_id)
            diff = (
                (total - menor_global)
                if total is not None and menor_global is not None
                else None
            )
            partes.append(f"<td>{_cel(diff)}</td>")
        else:
            partes.append(f"<td>{_cel(model.totais_gerais.diff_mensal.get(op_id))}</td>")
    partes.append("</tr>")

    if not seguro_novo:
        partes.append("<tr><td>Diferença anual</td><td>—</td>")
        for op_id in op_ids:
            partes.append(f"<td>{_cel(model.totais_gerais.diff_anual.get(op_id))}</td>")
        partes.append("</tr>")

    partes.append("</tbody></table></section>")
    return "".join(partes)


def render_html(model: PresentationViewModel) -> str:
    css = """
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; color: #1a1a1a; background: #f4f6f8; }
    .page { max-width: 1400px; margin: 0 auto; padding: 24px; background: #fff; min-height: 100vh; }
    @page { size: landscape; margin: 12mm; }
    @media print {
      body { background: #fff; }
      .page { page-break-after: always; max-width: none; padding: 12px; }
      .no-print { display: none; }
      .secao-regime { page-break-inside: avoid; }
    }
    header { border-bottom: 3px solid #0b5cab; padding-bottom: 12px; margin-bottom: 20px; }
    h1 { color: #0b5cab; margin: 0 0 4px; font-size: 1.6rem; }
    h2 { font-size: 1.15rem; color: #0b5cab; border-left: 4px solid #0b5cab; padding-left: 8px; }
    h3 { font-size: 1rem; color: #333; margin-top: 16px; }
    .sub { color: #555; margin: 0; }
    .rascunho { background: #fff3e0; border: 1px solid #ffb74d; padding: 8px 12px; margin: 12px 0; font-weight: 600; color: #e65100; }
    .aviso-pii { background: #fdecea; border: 1px solid #f5c2c0; padding: 8px 12px; margin: 12px 0; }
    .aviso-acomodacao { background: #fff8e1; border: 1px solid #ffe082; padding: 8px 12px; margin: 12px 0; color: #6d4c00; }
    .aviso-acomodacao ul { margin: 6px 0 0; padding-left: 1.2rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.78rem; margin: 12px 0 20px; }
    th, td { border: 1px solid #dde2e8; padding: 5px 6px; text-align: left; vertical-align: top; }
    th { background: #e8f0fa; color: #0b5cab; }
    tfoot td { background: #f4f6f8; font-weight: 600; }
    .secao-regime { margin-top: 28px; }
    .proposta-meta, .plano-meta { font-size: 0.85rem; color: #444; margin: 6px 0; }
    .totais-gerais { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
    .totais-gerais div { background: #f4f6f8; padding: 10px 14px; border-radius: 6px; min-width: 160px; }
    .totais-gerais strong { display: block; font-size: 0.72rem; color: #555; }
    .totais-secao { margin-top: 12px; }
    .ressalvas { font-size: 0.9rem; color: #444; margin-top: 20px; }
    .pagina-faixas { margin-bottom: 24px; page-break-inside: avoid; }
    """

    partes = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>{html.escape(model.titulo)}</title>",
        f"<style>{css}</style></head><body>",
    ]

    pagina_idx = 0

    def nova_pagina(conteudo: list[str]) -> None:
        nonlocal pagina_idx
        partes.append(f"<div class='page'>")
        partes.extend(conteudo)
        partes.append("</div>")
        pagina_idx += 1

    cabecalho = [
        "<header>",
        f"<h1>{html.escape(model.titulo)}</h1>",
        f"<p class='sub'>{html.escape(model.subtitulo or '')} · {html.escape(model.data_apresentacao)}</p>",
        "</header>",
        f"<div class='rascunho'>{html.escape(model.aviso_rascunho_interno)}</div>",
    ]
    if model.avisos_acomodacao:
        cabecalho.append("<div class='aviso-acomodacao'><strong>Atenção — acomodação</strong><ul>")
        for aviso in model.avisos_acomodacao:
            cabecalho.append(f"<li>{html.escape(aviso)}</li>")
        cabecalho.append("</ul></div>")
    if model.modo == "beneficiario":
        cabecalho.append(
            "<div class='aviso-pii'>Este material contém nomes de beneficiários. "
            "Mantenha em armazenamento privado.</div>"
        )

    tg = model.totais_gerais
    rotulos = _mapa_rotulos_propostas(model)
    seguro_novo = model.formato == "novo"
    if tg.atual_centavos is not None or tg.propostas:
        cabecalho.append("<div class='totais-gerais'>")
        if not seguro_novo and tg.baseline_rotulo:
            cabecalho.append(
                f"<div><strong>Referência atual</strong>{html.escape(tg.baseline_rotulo)}</div>"
            )
        if not seguro_novo and tg.atual_centavos is not None:
            cabecalho.append(f"<div><strong>Total atual</strong>{_cel(tg.atual_centavos)}</div>")
        for op_id, total in tg.propostas.items():
            rotulo = rotulos.get(op_id, "Proposta")
            cabecalho.append(f"<div><strong>{html.escape(rotulo)}</strong>{_cel(total)}</div>")
        if not seguro_novo:
            for op_id, diff in tg.diff_mensal.items():
                if diff is not None:
                    rotulo = rotulos.get(op_id, "Proposta")
                    cabecalho.append(
                        f"<div><strong>Δ mensal {html.escape(rotulo)}</strong>{_cel(diff)}</div>"
                    )
        cabecalho.append("</div>")

    nova_pagina(cabecalho)

    if model.modo == "resumo":
        op_ids = model.propostas_selecionadas
        for i in range(0, max(len(op_ids), 1), MAX_PROPOSTAS_POR_PAGINA):
            chunk = op_ids[i : i + MAX_PROPOSTAS_POR_PAGINA]
            nova_pagina(
                [_render_resumo(model, rotulos, chunk, seguro_novo=seguro_novo)]
            )

    for secao in model.secoes_regime:
        for pagina in secao.paginas_faixas:
            if model.modo != "faixas":
                continue
            bloco = [
                f"<section class='secao-regime'>",
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
            nova_pagina(bloco)

    if model.modo == "beneficiario" and model.beneficiarios:
        op_ids = model.propostas_selecionadas
        rotulos = _mapa_rotulos_propostas(model)
        for i in range(0, len(op_ids), MAX_PROPOSTAS_POR_PAGINA):
            chunk = op_ids[i : i + MAX_PROPOSTAS_POR_PAGINA]
            bloco = ["<section class='secao-regime'><h2>Detalhamento por beneficiário</h2>"]
            bloco.append("<table><thead><tr>")
            bloco.append(
                "<th>Nome</th><th>Idade</th><th>Faixa</th><th>Parentesco</th>"
                "<th>Plano atual</th><th>Vigente</th><th>Reajustado</th>"
            )
            for op_id in chunk:
                rotulo = rotulos.get(op_id, "Proposta")
                bloco.append(f"<th>{html.escape(rotulo)}<br><small>Valor · Δ</small></th>")
            bloco.append("</tr></thead><tbody>")
            for b in model.beneficiarios:
                bloco.append(
                    f"<tr><td>{html.escape(b.nome)}</td>"
                    f"<td>{b.idade if b.idade is not None else '—'}</td>"
                    f"<td>{html.escape(b.faixa_rotulo or '—')}</td>"
                    f"<td>{html.escape(b.parentesco or '—')}</td>"
                    f"<td>{html.escape(b.plano_atual or '—')}</td>"
                    f"<td>{_cel(b.atual_vigente_centavos)}</td>"
                    f"<td>{_cel(b.atual_reajustado_centavos)}</td>"
                )
                for op_id in chunk:
                    col = next((c for c in b.propostas if c.opcao_id == op_id), None)
                    bloco.append(
                        f"<td>{_cel(col.valor_centavos if col else None)}"
                        f"<br><small>{_cel(col.diff_centavos if col else None)}</small></td>"
                    )
                bloco.append("</tr>")
            bloco.append("</tbody></table></section>")
            nova_pagina(bloco)

    if model.ressalvas:
        partes.append("<div class='page'><section class='ressalvas'><h3>Ressalvas comerciais</h3><ul>")
        for r in model.ressalvas:
            partes.append(f"<li>{html.escape(r)}</li>")
        partes.append("</ul></section></div>")

    partes.append("</body></html>")
    return "".join(partes)
