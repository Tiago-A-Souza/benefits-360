"""Tabelas densas do resumo e das faixas — blocos de coluna por regime."""

from __future__ import annotations

import html
from dataclasses import dataclass, field

from newport_app.cotacao_pdf.faixas import ROTULOS_FAIXA
from newport_app.models.presentation import (
    PlanoAtualApresentacao,
    PresentationViewModel,
    PropostaApresentacao,
    SecaoRegimeApresentacao,
)
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA
from newport_app.presentation.colisao_coluna import coluna_bate, id_coluna_vm
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.reajuste import formatar_rotulo_reajuste_bps

_AUSENCIA = "—"
_PLANO_SINTETICO = "vidas-incluidas"
ROTULO_COLUNA_ATUAL = "Contrato atual"

# Preenchido pelo html_renderer para o harness (mutação de rótulo) enxergar o cabeçalho.
rotulo_coluna_hook = None


def _planos_reais(secao: SecaoRegimeApresentacao) -> list[PlanoAtualApresentacao]:
    return [p for p in secao.planos_atuais if p.subgrupo_id != _PLANO_SINTETICO]


def _prop(model: PresentationViewModel, op_id: str) -> PropostaApresentacao | None:
    for secao in model.secoes_regime:
        for p in secao.propostas:
            if id_coluna_vm(p) == op_id:
                return p
    return None


def _secao_da_proposta(model: PresentationViewModel, op_id: str) -> SecaoRegimeApresentacao | None:
    for secao in model.secoes_regime:
        if any(id_coluna_vm(p) == op_id for p in secao.propostas):
            return secao
    return None


def _cel_money(centavos: int | None, *, diff: bool = False) -> str:
    if centavos is None:
        return ""
    bruto = formatar_reais(centavos)
    sinal = "-" if bruto.startswith("-") else ""
    numero = bruto[1:].replace("R$ ", "") if sinal else bruto.replace("R$ ", "")
    cls = ["money", "n"]
    if diff and centavos < 0:
        cls.append("neg")
    elif diff and centavos > 0:
        cls.append("pos")
    return (
        f"<span class='{' '.join(cls)}' aria-label='{html.escape(bruto, quote=True)}'>"
        f"<span class='rs' aria-hidden='true'>{sinal}R$</span>"
        f"<span class='vl' aria-hidden='true'>{html.escape(numero)}</span></span>"
    )


def _texto_unico(valores: list[str | None]) -> tuple[str, bool]:
    limpos = [((v or "").strip() or _AUSENCIA) for v in valores] or [_AUSENCIA]
    if len(set(limpos)) == 1:
        return limpos[0], True
    return "", False


@dataclass
class BlocoColuna:
    rotulo: str
    atual: bool = False
    planos: list[PlanoAtualApresentacao] = field(default_factory=list)
    op_ids: list[str] = field(default_factory=list)
    acomodacao: str = _AUSENCIA
    acomodacao_por_col: list[str] = field(default_factory=list)
    acomodacao_span: bool = True
    modalidade: str = _AUSENCIA
    modalidade_por_col: list[str] = field(default_factory=list)
    modalidade_span: bool = True

    @property
    def n_cols(self) -> int:
        """Atual é um contrato: sempre uma coluna, N vigentes viram linhas."""
        if self.atual:
            return 1 if self.planos else 0
        return len(self.op_ids)

    def com_op_ids(self, op_ids: list[str]) -> BlocoColuna:
        if self.atual:
            return self
        escolhidos = [o for o in self.op_ids if o in op_ids]
        if not escolhidos:
            return BlocoColuna(rotulo=self.rotulo, atual=False)
        idx = {o: i for i, o in enumerate(self.op_ids)}
        acs = [self.acomodacao_por_col[idx[o]] for o in escolhidos] if self.acomodacao_por_col else []
        mds = [self.modalidade_por_col[idx[o]] for o in escolhidos] if self.modalidade_por_col else []
        ac_txt, ac_span = _texto_unico(acs) if acs else (self.acomodacao, True)
        md_txt, md_span = _texto_unico(mds) if mds else (self.modalidade, True)
        return BlocoColuna(
            rotulo=self.rotulo,
            atual=False,
            op_ids=escolhidos,
            acomodacao=ac_txt,
            acomodacao_por_col=acs,
            acomodacao_span=ac_span,
            modalidade=md_txt,
            modalidade_por_col=mds,
            modalidade_span=md_span,
        )


def montar_blocos(
    model: PresentationViewModel,
    op_ids: list[str],
    *,
    seguro_novo: bool,
) -> list[BlocoColuna]:
    blocos: list[BlocoColuna] = []
    if not seguro_novo:
        planos: list[PlanoAtualApresentacao] = []
        vistos: set[str] = set()
        secao_ref: SecaoRegimeApresentacao | None = None
        for secao in model.secoes_regime:
            for pl in _planos_reais(secao):
                if pl.subgrupo_id in vistos:
                    continue
                vistos.add(pl.subgrupo_id)
                planos.append(pl)
                if secao_ref is None:
                    secao_ref = secao
        if planos:
            acs = [p.acomodacao for p in planos]
            mds = [p.modalidade for p in planos]
            ac, ac_span = _texto_unico(acs)
            md, md_span = _texto_unico(mds)
            rotulo_reg = (secao_ref.regime_rotulo if secao_ref else "contrato atual")
            blocos.append(
                BlocoColuna(
                    rotulo=f"Plano atual · {rotulo_reg}",
                    atual=True,
                    planos=planos,
                    acomodacao=ac,
                    acomodacao_por_col=[(a or "").strip() or _AUSENCIA for a in acs],
                    acomodacao_span=ac_span,
                    modalidade=md,
                    modalidade_por_col=[(m or "").strip() or _AUSENCIA for m in mds],
                    modalidade_span=md_span,
                )
            )
    for secao in model.secoes_regime:
        ids = [
            oid
            for oid in op_ids
            if any(id_coluna_vm(p) == oid for p in secao.propostas)
        ]
        if not ids:
            continue
        props = [_prop(model, oid) for oid in ids]
        acs = [p.acomodacao if p else None for p in props]
        mds = [p.modalidade if p else None for p in props]
        ac, ac_span = _texto_unico(acs)
        md, md_span = _texto_unico(mds)
        blocos.append(
            BlocoColuna(
                rotulo=f"Propostas {secao.regime_rotulo}",
                op_ids=ids,
                acomodacao=ac,
                acomodacao_por_col=[(a or "").strip() or _AUSENCIA for a in acs],
                acomodacao_span=ac_span,
                modalidade=md,
                modalidade_por_col=[(m or "").strip() or _AUSENCIA for m in mds],
                modalidade_span=md_span,
            )
        )
    return [b for b in blocos if b.n_cols > 0]


def _pct_exibicao_cabecalho(percentual: str | None) -> str | None:
    """Remove o «+» das células; mantém «-» e decimais («11,98%»)."""
    if not percentual:
        return None
    return percentual[1:] if percentual.startswith("+") else percentual


def _percentual_unico_planos(planos: list[PlanoAtualApresentacao]) -> str | None:
    """Taxa única de todos os planos da coluna; None se faltar ou se divergirem."""
    vistos: set[str] = set()
    for pl in planos:
        pct = pl.reajuste_percentual_exibicao
        if not pct:
            return None
        vistos.add(pct)
    if len(vistos) == 1:
        return next(iter(vistos))
    return None


def _th_col_atual(
    planos: list[PlanoAtualApresentacao],
    *,
    percentual: str | None = None,
) -> str:
    ops = sorted(
        {(p.operadora or "").strip() for p in planos if (p.operadora or "").strip()}
    )
    operadora = ops[0] if len(ops) == 1 else ""
    od = (
        f"<span class='od' data-l='{html.escape(operadora, quote=True)}'></span>"
        if operadora
        else ""
    )
    rotulo = ROTULO_COLUNA_ATUAL
    pct = _pct_exibicao_cabecalho(percentual)
    if pct:
        rotulo = f"{ROTULO_COLUNA_ATUAL} {pct}"
    return (
        f"<th class='atual'><span class='op'>{html.escape(rotulo)}</span>"
        f"{od}</th>"
    )


def _th_col_prop(prop: PropostaApresentacao | None, nome: str) -> str:
    operadora = ((prop.operadora if prop else "") or "").strip()
    od = (
        f"<span class='od' data-l='{html.escape(operadora, quote=True)}'></span>"
        if operadora
        else ""
    )
    if prop is not None and prop.misto:
        indice = prop.indice_cenario or 1
        titulo = f"Cenário {indice}"
        return (
            f"<th title='{html.escape(titulo + ' · ' + nome, quote=True)}'>"
            f"<span class='pl'>{html.escape(titulo)}</span>"
            f"<span class='op'>{html.escape(nome)}</span>{od}</th>"
        )
    return (
        f"<th title='{html.escape(nome, quote=True)}'>"
        f"<span class='op'>{html.escape(nome)}</span>{od}</th>"
    )


def _cabecalho_blocos(
    blocos: list[BlocoColuna],
    model: PresentationViewModel,
    rotulos: dict[str, str],
    *,
    primeira: str,
    extras: str = "",
    percentual_atual: str | None = None,
) -> str:
    n_extras = extras.count("<th")
    partes = ["<thead>"]
    partes.append("<tr class='bloco-regime'>")
    partes.append(f"<th rowspan='2'>{html.escape(primeira)}</th>")
    partes.append(extras)
    for b in blocos:
        cls = " class='atual'" if b.atual else ""
        partes.append(
            f"<th{cls} colspan='{b.n_cols}'>{html.escape(b.rotulo)}</th>"
        )
    partes.append("</tr><tr class='bloco-plano'>")
    for b in blocos:
        if b.atual:
            partes.append(_th_col_atual(b.planos, percentual=percentual_atual))
        else:
            for oid in b.op_ids:
                prop = _prop(model, oid)
                nome = rotulos.get(oid, "Proposta")
                if rotulo_coluna_hook is not None:
                    nome = rotulo_coluna_hook(
                        oid,
                        [p for s in model.secoes_regime for p in s.propostas],
                        rotulos,
                    )
                partes.append(_th_col_prop(prop, nome))
    partes.append("</tr></thead>")
    del n_extras
    return "".join(partes)


def _td_meta(bloco: BlocoColuna, *, campo: str) -> str:
    span = bloco.acomodacao_span if campo == "acomodacao" else bloco.modalidade_span
    texto = bloco.acomodacao if campo == "acomodacao" else bloco.modalidade
    por = bloco.acomodacao_por_col if campo == "acomodacao" else bloco.modalidade_por_col
    cls = " class='atual'" if bloco.atual else ""
    if span:
        return f"<td{cls} colspan='{bloco.n_cols}'>{html.escape(texto)}</td>"
    if bloco.atual:
        pares = []
        for pl, v in zip(bloco.planos, por):
            pares.append(
                "<span class='atual-item'>"
                f"<span class='atual-pl'>{html.escape(pl.plano_nome)}</span>"
                f"{html.escape(v)}"
                "</span>"
            )
        return f"<td class='atual'>{''.join(pares) or _AUSENCIA}</td>"
    partes = []
    for v in por:
        partes.append(f"<td{cls}>{html.escape(v)}</td>")
    return "".join(partes)


def _linha_topo(blocos: list[BlocoColuna], rotulo: str, campo: str) -> str:
    cls = "linha-topo" if rotulo == "Acomodação" else "linha-topo linha-topo-extra"
    partes = [f"<tr class='{cls}'><td>{html.escape(rotulo)}</td>"]
    for b in blocos:
        partes.append(_td_meta(b, campo=campo))
    partes.append("</tr>")
    return "".join(partes)


def _indicador_de(model: PresentationViewModel, rotulo: str, op_id: str | None, *, atual: bool):
    for secao in model.secoes_regime:
        for lin in secao.indicadores_resumo:
            if lin.rotulo != rotulo:
                continue
            if atual:
                return lin.atual
            if op_id is not None:
                if op_id in lin.propostas:
                    return lin.propostas[op_id]
                continue
    return None


def _td_cel_indicador(cel, *, como_diff: bool, atual: bool) -> str:
    cls = " class='atual'" if atual else ""
    vazio = f"<td{cls}>{_AUSENCIA if atual else ''}</td>"
    if cel is None:
        return vazio
    if cel.referencia and (cel.centavos is None or cel.centavos == 0):
        return f"<td{cls}>{html.escape(cel.texto or 'referência')}</td>"
    if cel.ausente:
        txt = (cel.texto or "").strip() or _AUSENCIA
        return f"<td{cls}>{html.escape(txt)}</td>"
    if cel.texto is not None and cel.centavos is None and cel.bps is None:
        return f"<td{cls}>{html.escape(cel.texto)}</td>"
    if cel.centavos is not None:
        base = _cel_money(cel.centavos, diff=como_diff)
        if cel.bps is not None:
            pct = html.escape(formatar_rotulo_reajuste_bps(cel.bps))
            return f"<td{cls}>{base}<span class='ajuste'> ({pct})</span></td>"
        return f"<td{cls}>{base}</td>"
    if cel.bps is not None:
        return f"<td{cls}>{html.escape(formatar_rotulo_reajuste_bps(cel.bps))}</td>"
    return vazio


def _subtotal_proposta_plano(plano: PlanoAtualApresentacao, op_id: str) -> int | None:
    vals = [
        col.subtotal_centavos
        for fx in plano.faixas
        for col in fx.propostas
        if coluna_bate(col, op_id) and col.subtotal_centavos is not None
    ]
    return sum(vals) if vals else None


def _subtotal_proposta_todas_secoes(
    model: PresentationViewModel, subgrupo_id: str, op_id: str
) -> int | None:
    """Subtotal do grupo na coluna — vem do recorte do cenário, não da faixa."""
    prop = _prop(model, op_id)
    if prop is not None and subgrupo_id in prop.subtotais_por_subgrupo:
        return prop.subtotais_por_subgrupo[subgrupo_id]
    for secao in model.secoes_regime:
        for pl in secao.planos_atuais:
            if pl.subgrupo_id != subgrupo_id:
                continue
            valor = _subtotal_proposta_plano(pl, op_id)
            if valor is not None:
                return valor
    return None


def _tem_coluna_proposta(model: PresentationViewModel, subgrupo_id: str, op_id: str) -> bool:
    prop = _prop(model, op_id)
    if prop is not None and subgrupo_id in prop.subtotais_por_subgrupo:
        return True
    for secao in model.secoes_regime:
        for pl in secao.planos_atuais:
            if pl.subgrupo_id != subgrupo_id:
                continue
            if any(coluna_bate(col, op_id) for fx in pl.faixas for col in fx.propostas):
                return True
    return False


def _contrato_atual_html(centavos: int | None, percentual: str | None) -> str:
    if centavos is None and not percentual:
        return _AUSENCIA
    valor = _cel_money(centavos)
    if percentual:
        return f"{valor}<span class='ajuste'>{html.escape(percentual)}</span>"
    return valor or _AUSENCIA


def _linha_indicador(
    model: PresentationViewModel,
    blocos: list[BlocoColuna],
    rotulo: str,
    *,
    extra_tds: str = "",
    destaque: bool = False,
) -> str:
    como_diff = rotulo.startswith("Diferença") or rotulo.startswith("Variação")
    cls = " class='destaque'" if destaque else ""
    partes = [f"<tr{cls}><td>{html.escape(rotulo)}</td>", extra_tds]
    for b in blocos:
        if b.atual:
            cel = _indicador_de(model, rotulo, None, atual=True)
            partes.append(_td_cel_indicador(cel, como_diff=como_diff, atual=True))
        else:
            for oid in b.op_ids:
                cel = _indicador_de(model, rotulo, oid, atual=False)
                partes.append(_td_cel_indicador(cel, como_diff=como_diff, atual=False))
    partes.append("</tr>")
    return "".join(partes)


def render_tabela_resumo(
    model: PresentationViewModel,
    op_ids: list[str],
    rotulos: dict[str, str],
    *,
    seguro_novo: bool,
) -> str:
    blocos = montar_blocos(model, op_ids, seguro_novo=seguro_novo)
    planos_atual: list[PlanoAtualApresentacao] = []
    for b in blocos:
        if b.atual:
            planos_atual = b.planos
            break
    pct_cabecalho = (
        None if seguro_novo else _percentual_unico_planos(planos_atual)
    )
    partes = ["<div class='rolo'><table class='tabela-densa tabela-resumo'>"]
    partes.append(
        _cabecalho_blocos(
            blocos,
            model,
            rotulos,
            primeira="Indicador",
            percentual_atual=pct_cabecalho,
        )
    )
    partes.append("<tbody>")
    partes.append(_linha_topo(blocos, "Acomodação", "acomodacao"))
    partes.append(_linha_topo(blocos, "Modalidade", "modalidade"))

    if not seguro_novo:
        planos = planos_atual
        for plano in planos:
            vidas = sum(fx.qtd_total for fx in plano.faixas)
            vidas_attr = f" data-vidas='{vidas}'" if vidas > 0 else ""
            partes.append(f"<tr><td{vidas_attr}>{html.escape(plano.plano_nome)}</td>")
            pct_cel = None if pct_cabecalho else plano.reajuste_percentual_exibicao
            for b in blocos:
                if b.atual:
                    partes.append(
                        "<td class='atual'>"
                        + _contrato_atual_html(
                            plano.subtotal_reajustado_centavos,
                            pct_cel,
                        )
                        + "</td>"
                    )
                else:
                    for oid in b.op_ids:
                        valor = _subtotal_proposta_todas_secoes(
                            model, plano.subgrupo_id, oid
                        )
                        prop = _prop(model, oid)
                        nome_atr = (
                            (prop.nomes_atribuidos_por_subgrupo.get(plano.subgrupo_id) or "")
                            if prop
                            else ""
                        )
                        if valor is not None:
                            rotulo = (
                                f"<span class='pl-cel'>{html.escape(nome_atr)}</span>"
                                if nome_atr
                                else ""
                            )
                            partes.append(f"<td>{rotulo}{_cel_money(valor)}</td>")
                        else:
                            partes.append(
                                "<td>Sem valor neste plano</td>"
                                if _tem_coluna_proposta(model, plano.subgrupo_id, oid)
                                else "<td></td>"
                            )
            partes.append("</tr>")
        if planos:
            partes.append("<tr data-row='consolidado'><td><strong>Consolidado</strong></td>")
            reaj_c = sum((p.subtotal_reajustado_centavos or 0) for p in planos) or None
            pct = None if pct_cabecalho else model.reajuste_consolidado_percentual_exibicao
            for b in blocos:
                if b.atual:
                    partes.append(
                        "<td class='atual'><strong>"
                        + _contrato_atual_html(reaj_c, pct)
                        + "</strong></td>"
                    )
                else:
                    for oid in b.op_ids:
                        total = model.totais_gerais.propostas.get(oid)
                        partes.append(f"<td><strong>{_cel_money(total)}</strong></td>")
            partes.append("</tr>")

    skip = {"Acomodação"}
    vistos: set[str] = set(skip)
    for secao in model.secoes_regime:
        for lin in secao.indicadores_resumo:
            if lin.rotulo in vistos:
                continue
            if lin.grupo == "cabecalho" and lin.rotulo == "Acomodação":
                continue
            vistos.add(lin.rotulo)
            partes.append(
                _linha_indicador(
                    model,
                    blocos,
                    lin.rotulo,
                    destaque=lin.destaque,
                )
            )

    partes.append("</tbody></table></div>")
    return "".join(partes)


def _faixa_do_plano(plano: PlanoAtualApresentacao, rotulo: str):
    return next((fx for fx in plano.faixas if fx.rotulo == rotulo), None)


def _valor_faixa_atual(fx) -> tuple[int | None, str | None]:
    if fx is None:
        return None, None
    if fx.atual_reajustado_unitario_centavos is not None:
        return fx.atual_reajustado_unitario_centavos, None
    return fx.atual_reajustado_total_centavos, None


def _valor_faixa_prop(fx, op_id: str) -> int | None:
    if fx is None:
        return None
    col = next((c for c in fx.propostas if coluna_bate(c, op_id)), None)
    if col is None or col.quantidade == 0:
        return None
    return col.valor_unitario_centavos


def _html_unitarios_atual(planos: list[PlanoAtualApresentacao], rotulo_fx: str) -> str:
    """Uma célula: unitário único, ou os dois valores rotulados se divergirem."""
    itens: list[tuple[str, int]] = []
    for pl in planos:
        fx = _faixa_do_plano(pl, rotulo_fx)
        unit, _ = _valor_faixa_atual(fx)
        if unit is None:
            continue
        itens.append((pl.plano_nome, unit))
    if not itens:
        return _AUSENCIA
    if len({u for _, u in itens}) == 1:
        return _cel_money(itens[0][1]) or _AUSENCIA
    partes = []
    for nome, unit in itens:
        partes.append(
            "<span class='atual-item'>"
            f"<span class='atual-pl'>{html.escape(nome)}</span>"
            f"{_cel_money(unit)}"
            "</span>"
        )
    return "".join(partes)


def render_tabela_faixas(
    model: PresentationViewModel,
    op_ids: list[str],
    rotulos: dict[str, str],
    *,
    seguro_novo: bool,
) -> str:
    blocos = montar_blocos(model, op_ids, seguro_novo=seguro_novo)
    cabeca = (
        "<h4>Comparativo entre propostas</h4>"
        if seguro_novo
        else "<h4>Plano atual</h4>"
    )
    planos: list[PlanoAtualApresentacao] = []
    for b in blocos:
        if b.atual:
            planos = b.planos
            break
    if not planos:
        for secao in model.secoes_regime:
            planos.extend(_planos_reais(secao) or secao.planos_atuais)
            if planos:
                break
    extras = (
        "<th class='col-titdep' rowspan='2'>Tit.</th>"
        "<th class='col-titdep' rowspan='2'>Dep.</th>"
        "<th class='col-vidas' rowspan='2'>Vidas</th>"
    )
    partes = [cabeca, "<div class='rolo'><table class='tabela-faixas tabela-densa'>"]
    partes.append(
        _cabecalho_blocos(
            blocos, model, rotulos, primeira="Faixa", extras=extras
        )
    )
    partes.append("<tbody>")
    partes.append(_linha_topo_faixas(blocos, "Acomodação", "acomodacao"))
    partes.append(_linha_topo_faixas(blocos, "Modalidade", "modalidade"))
    partes.append(_linha_validade_faixas(model, blocos))

    rotulos_linhas = list(ROTULOS_FAIXA)
    existentes = []
    for pl in planos:
        for fx in pl.faixas:
            if fx.rotulo not in rotulos_linhas and fx.rotulo not in existentes:
                existentes.append(fx.rotulo)
    rotulos_linhas.extend(existentes)

    for rotulo_fx in rotulos_linhas:
        faixas_planos = [_faixa_do_plano(pl, rotulo_fx) for pl in planos]
        tit = sum((fx.qtd_titulares if fx else 0) for fx in faixas_planos)
        dep = sum((fx.qtd_dependentes if fx else 0) for fx in faixas_planos)
        vidas = sum((fx.qtd_total if fx else 0) for fx in faixas_planos)
        if not any(faixas_planos) and not planos:
            # Seguro novo: faixas vêm do plano sintético.
            for secao in model.secoes_regime:
                for pl in secao.planos_atuais:
                    fx = _faixa_do_plano(pl, rotulo_fx)
                    if fx:
                        tit += fx.qtd_titulares
                        dep += fx.qtd_dependentes
                        vidas += fx.qtd_total
                        faixas_planos.append(fx)
        partes.append(f"<tr><td>{html.escape(rotulo_fx)}</td>")
        partes.append(
            f"<td class='col-titdep'>{tit}</td>"
            f"<td class='col-titdep'>{dep}</td>"
            f"<td class='col-vidas'>{vidas}</td>"
        )
        for b in blocos:
            if b.atual:
                partes.append(
                    f"<td class='atual'>{_html_unitarios_atual(b.planos, rotulo_fx)}</td>"
                )
            else:
                for oid in b.op_ids:
                    valor = None
                    for secao in model.secoes_regime:
                        for pl in secao.planos_atuais:
                            valor = _valor_faixa_prop(
                                _faixa_do_plano(pl, rotulo_fx), oid
                            )
                            if valor is not None:
                                break
                        if valor is not None:
                            break
                    partes.append(
                        f"<td>{_cel_money(valor)}</td>" if valor is not None else "<td></td>"
                    )
        partes.append("</tr>")

    partes.append("</tbody><tfoot><tr><td>Totais</td>")
    partes.append("<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>")
    for b in blocos:
        if b.atual:
            reaj_c = sum((p.subtotal_reajustado_centavos or 0) for p in b.planos) or None
            pct = model.reajuste_consolidado_percentual_exibicao
            partes.append(
                "<td class='atual'>"
                + _contrato_atual_html(reaj_c, pct)
                + "</td>"
            )
        else:
            for oid in b.op_ids:
                total = model.totais_gerais.propostas.get(oid)
                if total is None:
                    for secao in model.secoes_regime:
                        total = secao.totais.propostas.get(oid)
                        if total is not None:
                            break
                partes.append(f"<td>{_cel_money(total)}</td>")
    partes.append("</tr>")
    if not seguro_novo:
        partes.append("<tr><td>Diferença mensal</td>")
        partes.append("<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>")
        for b in blocos:
            if b.atual:
                partes.append(f"<td class='atual'>referência</td>")
            else:
                for oid in b.op_ids:
                    partes.append(f"<td>{_cel_money(model.totais_gerais.diff_mensal.get(oid), diff=True)}</td>")
        partes.append("</tr><tr><td>Diferença anual</td>")
        partes.append("<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>")
        for b in blocos:
            if b.atual:
                partes.append(f"<td class='atual'>{_AUSENCIA}</td>")
            else:
                for oid in b.op_ids:
                    partes.append(f"<td>{_cel_money(model.totais_gerais.diff_anual.get(oid), diff=True)}</td>")
        partes.append("</tr>")
    partes.append("</tfoot></table></div>")
    return "".join(partes)


def _linha_topo_faixas(blocos: list[BlocoColuna], rotulo: str, campo: str) -> str:
    cls = "linha-topo" if rotulo == "Acomodação" else "linha-topo linha-topo-extra"
    partes = [f"<tr class='{cls}'><td>{html.escape(rotulo)}</td>"]
    partes.append(
        "<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>"
    )
    for b in blocos:
        partes.append(_td_meta(b, campo=campo))
    partes.append("</tr>")
    return "".join(partes)


def _linha_validade_faixas(
    model: PresentationViewModel, blocos: list[BlocoColuna]
) -> str:
    partes = [
        "<tr class='linha-topo linha-topo-extra'><td>Validade</td>",
        "<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>",
    ]
    for b in blocos:
        if b.atual:
            partes.append(f"<td class='atual'>{_AUSENCIA}</td>")
        else:
            for oid in b.op_ids:
                prop = _prop(model, oid)
                val = ((prop.validade if prop else None) or "").strip()
                texto = f"Validade: {val}" if val else ""
                partes.append(f"<td>{html.escape(texto)}</td>")
    partes.append("</tr>")
    return "".join(partes)


def envelopar_tela_impressao(
    html_completo: str,
    html_chunks: list[str],
) -> str:
    """Tela: uma tabela. Impressão: um bloco por chunk de propostas."""
    if len(html_chunks) <= 1:
        return html_completo
    partes = [f"<div class='layout-tela'>{html_completo}</div>", "<div class='layout-impressao'>"]
    for chunk in html_chunks:
        partes.append(chunk)
    partes.append("</div>")
    return "".join(partes)


def chunks_propostas(op_ids: list[str]) -> list[list[str]]:
    if not op_ids:
        return [[]]
    return [
        op_ids[i : i + MAX_PROPOSTAS_POR_PAGINA]
        for i in range(0, len(op_ids), MAX_PROPOSTAS_POR_PAGINA)
    ]
