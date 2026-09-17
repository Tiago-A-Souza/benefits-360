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
from newport_app.presentation.nome_plano_exibicao import (
    encurtar_nome_plano_exibicao,
    nome_plano_cabecalho,
    nome_plano_documento,
)
from newport_app.presentation.reajuste import formatar_rotulo_reajuste_bps

_AUSENCIA = "—"
_PLANO_SINTETICO = "vidas-incluidas"
ROTULO_COLUNA_ATUAL = "Contrato atual"

# Preenchido pelo html_renderer para o harness (mutação de rótulo) enxergar o cabeçalho.
rotulo_coluna_hook = None


def html_linhas_nome_plano(nome: str) -> str:
    """Quebra «A + B» em linhas. O nome inteiro continua no title da coluna."""
    partes = [p.strip() for p in (nome or "").split(" + ") if p.strip()]
    if len(partes) < 2:
        return html.escape(nome or "")
    linhas = [f"<span class='op-linha'>{html.escape(partes[0])}</span>"]
    for parte in partes[1:]:
        linhas.append(
            f"<span class='op-linha'><span class='op-mais'>+</span> {html.escape(parte)}</span>"
        )
    return " ".join(linhas)


def html_linhas_nome_plano_documento(
    nome: str,
    *,
    modalidade: str | None = None,
) -> str:
    """Cabeçalho do documento: encurta e opcionalmente acrescenta modalidade."""
    partes = [p.strip() for p in (nome or "").split(" + ") if p.strip()]
    if not partes:
        return ""
    mod_unica = modalidade if len(partes) == 1 else None
    curtos: list[str] = []
    for parte in partes:
        curto, _, _ = nome_plano_cabecalho(parte, modalidade=mod_unica)
        curtos.append(curto)
    if len(curtos) < 2:
        return html.escape(curtos[0])
    linhas = [f"<span class='op-linha'>{html.escape(curtos[0])}</span>"]
    for curto in curtos[1:]:
        linhas.append(
            f"<span class='op-linha'><span class='op-mais'>+</span> {html.escape(curto)}</span>"
        )
    return " ".join(linhas)


def coletar_notas_cobertura(*nomes: str | None) -> list[tuple[str, str]]:
    """Pares (nome curto, abrangência) extraídos dos nomes completos."""
    vistos: set[tuple[str, str]] = set()
    notas: list[tuple[str, str]] = []
    for nome in nomes:
        if not (nome or "").strip():
            continue
        for parte in (p.strip() for p in nome.split(" + ") if p.strip()):
            curto, abr = encurtar_nome_plano_exibicao(parte)
            if not abr:
                continue
            chave = (curto.casefold(), abr.casefold())
            if chave in vistos:
                continue
            vistos.add(chave)
            notas.append((curto, abr))
    return notas


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


def planos_das_faixas(
    model: PresentationViewModel, *, seguro_novo: bool
) -> list[PlanoAtualApresentacao]:
    """Vigentes únicos, na ordem em que aparecem — uma seção de faixas cada."""
    if seguro_novo:
        for secao in model.secoes_regime:
            if secao.planos_atuais:
                return list(secao.planos_atuais)
        return []
    vistos: set[str] = set()
    planos: list[PlanoAtualApresentacao] = []
    for secao in model.secoes_regime:
        for pl in _planos_reais(secao):
            if pl.subgrupo_id in vistos:
                continue
            vistos.add(pl.subgrupo_id)
            planos.append(pl)
    return planos


def ids_do_grupo(
    model: PresentationViewModel, op_ids: list[str], plano: PlanoAtualApresentacao
) -> list[str]:
    """Colunas que este grupo vê.

    Sem mapa de atribuição (legado): todas as selecionadas, como a tela.
    Com mapa: só as que a fase 3 atribuiu a este subgrupo.
    """
    out: list[str] = []
    for oid in op_ids:
        prop = _prop(model, oid)
        if prop is None:
            out.append(oid)
            continue
        atribuidos = prop.nomes_atribuidos_por_subgrupo
        if atribuidos and plano.subgrupo_id not in atribuidos:
            continue
        out.append(oid)
    return out


def _meta_proposta_subgrupo(
    prop: PropostaApresentacao | None,
    subgrupo_id: str,
    *,
    campo: str,
) -> str | None:
    if prop is None:
        return None
    mapa = (
        prop.acomodacoes_por_subgrupo
        if campo == "acomodacao"
        else prop.modalidades_por_subgrupo
    )
    if subgrupo_id in mapa:
        return mapa[subgrupo_id]
    if not prop.misto:
        return prop.acomodacao if campo == "acomodacao" else prop.modalidade
    return prop.acomodacao if campo == "acomodacao" else prop.modalidade


def montar_blocos(
    model: PresentationViewModel,
    op_ids: list[str],
    *,
    seguro_novo: bool,
    plano: PlanoAtualApresentacao | None = None,
) -> list[BlocoColuna]:
    """Blocos de coluna. Sem `plano`: resumo (atual agregado). Com `plano`: faixas do grupo."""
    blocos: list[BlocoColuna] = []
    if not seguro_novo:
        if plano is not None:
            planos = [plano]
            secao_ref = _secao_da_proposta(model, op_ids[0]) if op_ids else None
            if secao_ref is None and model.secoes_regime:
                secao_ref = model.secoes_regime[0]
        else:
            planos = []
            vistos: set[str] = set()
            secao_ref = None
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
        if plano is not None:
            ids = ids_do_grupo(model, ids, plano)
        if not ids:
            continue
        props = [_prop(model, oid) for oid in ids]
        if plano is not None:
            sg = plano.subgrupo_id
            acs = [
                _meta_proposta_subgrupo(p, sg, campo="acomodacao") for p in props
            ]
            mds = [
                _meta_proposta_subgrupo(p, sg, campo="modalidade") for p in props
            ]
        else:
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


def modalidade_cabecalho_proposta(
    prop: PropostaApresentacao | None,
    subgrupo_id: str | None,
) -> str | None:
    if prop is None:
        return None
    if subgrupo_id:
        md = prop.modalidades_por_subgrupo.get(subgrupo_id)
        if md:
            return md
    if prop.misto:
        return None
    return prop.modalidade


def _modalidade_unica_planos(planos: list[PlanoAtualApresentacao]) -> str | None:
    mods = {(p.modalidade or "").strip() for p in planos if (p.modalidade or "").strip()}
    if len(mods) == 1:
        return mods.pop()
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
    mod = _modalidade_unica_planos(planos)
    if mod:
        rotulo = f"{rotulo} ({mod})"
    pct = _pct_exibicao_cabecalho(percentual)
    if pct:
        rotulo = f"{rotulo} {pct}"
    return (
        f"<th class='atual'><span class='cab-stack'>"
        f"<span class='op'>{html.escape(rotulo)}</span>{od}"
        f"</span></th>"
    )


def _th_col_prop(
    prop: PropostaApresentacao | None,
    nome: str,
    *,
    subgrupo_id: str | None = None,
) -> str:
    operadora = ((prop.operadora if prop else "") or "").strip()
    od = (
        f"<span class='od' data-l='{html.escape(operadora, quote=True)}'></span>"
        if operadora
        else ""
    )
    if prop is not None and subgrupo_id:
        atribuido = (prop.nomes_atribuidos_por_subgrupo.get(subgrupo_id) or "").strip()
        if atribuido:
            nome = atribuido
    mod = modalidade_cabecalho_proposta(prop, subgrupo_id)
    exib = html_linhas_nome_plano_documento(nome, modalidade=mod)
    if prop is not None and subgrupo_id:
        if prop.misto:
            indice = prop.indice_cenario or 1
            titulo = f"Cenário {indice}"
            return (
                f"<th title='{html.escape(titulo + ' · ' + nome, quote=True)}'>"
                f"<span class='cab-stack'>"
                f"<span class='pl'>{html.escape(titulo)}</span>"
                f"<span class='op'>{exib}</span>{od}"
                f"</span></th>"
            )
        return (
            f"<th title='{html.escape(nome, quote=True)}'><span class='cab-stack'>"
            f"<span class='op'>{exib}</span>{od}"
            f"</span></th>"
        )
    if prop is not None and prop.misto:
        indice = prop.indice_cenario or 1
        titulo = f"Cenário {indice}"
        return (
            f"<th title='{html.escape(titulo + ' · ' + nome, quote=True)}'>"
            f"<span class='cab-stack'>"
            f"<span class='pl'>{html.escape(titulo)}</span>"
            f"<span class='op'>{exib}</span>{od}"
            f"</span></th>"
        )
    return (
        f"<th title='{html.escape(nome, quote=True)}'><span class='cab-stack'>"
        f"<span class='op'>{exib}</span>{od}"
        f"</span></th>"
    )


def _cabecalho_blocos(
    blocos: list[BlocoColuna],
    model: PresentationViewModel,
    rotulos: dict[str, str],
    *,
    primeira: str,
    extras: str = "",
    percentual_atual: str | None = None,
    subgrupo_id: str | None = None,
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
                atribuido = ""
                if subgrupo_id and prop is not None:
                    atribuido = (
                        prop.nomes_atribuidos_por_subgrupo.get(subgrupo_id) or ""
                    ).strip()
                    if atribuido:
                        nome = atribuido
                    elif not prop.misto:
                        nome = (prop.plano_nome or nome).strip()
                if rotulo_coluna_hook is not None and not subgrupo_id:
                    nome = rotulo_coluna_hook(
                        oid,
                        [p for s in model.secoes_regime for p in s.propostas],
                        rotulos,
                    )
                partes.append(
                    _th_col_prop(prop, nome, subgrupo_id=subgrupo_id or None)
                )
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
                                f"<span class='pl-cel'>{html.escape(nome_plano_documento(nome_atr))}</span>"
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
    if col.valor_unitario_centavos is not None:
        return col.valor_unitario_centavos
    return col.subtotal_centavos


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


def _parentesco_totais_plano(
    model: PresentationViewModel,
    plano: PlanoAtualApresentacao | None,
    op_ids: list[str],
) -> tuple[int, int, dict[str, int], dict[str, int]]:
    if plano is not None:
        tit_props = {
            oid: (plano.subtotais_titular_propostas.get(oid) or 0) for oid in op_ids
        }
        dep_props = {
            oid: (plano.subtotais_dependente_propostas.get(oid) or 0) for oid in op_ids
        }
        return (
            plano.subtotal_titular_reajustado_centavos or 0,
            plano.subtotal_dependente_reajustado_centavos or 0,
            tit_props,
            dep_props,
        )
    tit = dep = 0
    tit_props: dict[str, int] = {oid: 0 for oid in op_ids}
    dep_props: dict[str, int] = {oid: 0 for oid in op_ids}
    for secao in model.secoes_regime:
        for pl in secao.planos_atuais:
            if pl.subgrupo_id == "vidas-incluidas":
                continue
            tit += pl.subtotal_titular_reajustado_centavos or 0
            dep += pl.subtotal_dependente_reajustado_centavos or 0
            for oid in op_ids:
                tit_props[oid] += pl.subtotais_titular_propostas.get(oid) or 0
                dep_props[oid] += pl.subtotais_dependente_propostas.get(oid) or 0
    return tit, dep, tit_props, dep_props


def _linha_total_parentesco_faixas(
    rotulo: str,
    blocos: list[BlocoColuna],
    model: PresentationViewModel,
    plano: PlanoAtualApresentacao | None,
    op_ids: list[str],
    *,
    campo: str,
    seguro_novo: bool,
) -> str:
    tit_total, dep_total, tit_props, dep_props = _parentesco_totais_plano(
        model, plano, op_ids
    )
    valor_atual = tit_total if campo == "titular" else dep_total
    props = tit_props if campo == "titular" else dep_props
    partes = [f"<tr><td>{html.escape(rotulo)}</td>"]
    partes.append(
        "<td class='col-titdep'></td>"
        "<td class='col-titdep'></td>"
        "<td class='col-vidas'></td>"
    )
    for b in blocos:
        if b.atual:
            if seguro_novo:
                continue
            partes.append(f"<td class='atual'>{_cel_money(valor_atual)}</td>")
        else:
            for oid in b.op_ids:
                partes.append(f"<td>{_cel_money(props.get(oid, 0))}</td>")
    partes.append("</tr>")
    return "".join(partes)


def _cabecalho_grupo(plano: PlanoAtualApresentacao) -> str:
    vidas = sum(fx.qtd_total for fx in plano.faixas)
    meta: list[str] = []
    if vidas:
        meta.append(f"{vidas} {'vida' if vidas == 1 else 'vidas'}")
    if (plano.modalidade or "").strip():
        meta.append(plano.modalidade.strip())
    if (plano.copart_descricao or "").strip():
        meta.append(plano.copart_descricao.strip())
    nome = html.escape(plano.plano_nome)
    if (plano.acomodacao or "").strip():
        nome = f"{nome} — {html.escape(plano.acomodacao.strip())}"
    return (
        "<div class='grupo-cab'>"
        f"<span class='g'><small>Grupo de beneficiários</small>{nome}</span>"
        f"<span class='q'>{html.escape(' · '.join(meta))}</span>"
        "</div>"
    )


def render_secao_faixas_grupo(
    model: PresentationViewModel,
    op_ids: list[str],
    rotulos: dict[str, str],
    plano: PlanoAtualApresentacao | None,
    *,
    seguro_novo: bool,
) -> str:
    """Uma tabela de faixas: o vigente deste grupo e só as colunas escolhidas para ele."""
    if plano is not None:
        for secao in model.secoes_regime:
            achado = next(
                (pl for pl in secao.planos_atuais if pl.subgrupo_id == plano.subgrupo_id),
                None,
            )
            if achado is not None:
                plano = achado
                break
    blocos = montar_blocos(model, op_ids, seguro_novo=seguro_novo, plano=plano)
    extras = (
        "<th class='col-titdep' rowspan='2'>Tit.</th>"
        "<th class='col-titdep' rowspan='2'>Dep.</th>"
        "<th class='col-vidas' rowspan='2'>Vidas</th>"
    )
    planos = [plano] if plano is not None else []
    if not planos:
        for secao in model.secoes_regime:
            planos.extend(secao.planos_atuais)
            if planos:
                break
    pct_cabecalho = None
    if plano is not None:
        pct_cabecalho = _pct_exibicao_cabecalho(plano.reajuste_percentual_exibicao)
    partes: list[str] = []
    if plano is not None and not seguro_novo:
        partes.append(_cabecalho_grupo(plano))
    elif seguro_novo:
        partes.append("<h4>Comparativo entre propostas</h4>")
    partes.append("<div class='rolo'><table class='tabela-faixas tabela-densa'>")
    partes.append(
        _cabecalho_blocos(
            blocos,
            model,
            rotulos,
            primeira="Faixa",
            extras=extras,
            percentual_atual=pct_cabecalho,
            subgrupo_id=plano.subgrupo_id if plano else None,
        )
    )
    partes.append("<tbody>")
    partes.append(_linha_topo_faixas(blocos, "Acomodação", "acomodacao"))
    partes.append(_linha_validade_faixas(model, blocos))

    rotulos_linhas = list(ROTULOS_FAIXA)
    existentes: list[str] = []
    for pl in planos:
        for fx in pl.faixas:
            if fx.rotulo not in rotulos_linhas and fx.rotulo not in existentes:
                existentes.append(fx.rotulo)
    rotulos_linhas.extend(existentes)

    vidas_total = 0
    for rotulo_fx in rotulos_linhas:
        faixas_planos = [_faixa_do_plano(pl, rotulo_fx) for pl in planos]
        tit = sum((fx.qtd_titulares if fx else 0) for fx in faixas_planos)
        dep = sum((fx.qtd_dependentes if fx else 0) for fx in faixas_planos)
        vidas = sum((fx.qtd_total if fx else 0) for fx in faixas_planos)
        if vidas == 0:
            continue
        vidas_total += vidas
        fx0 = next((fx for fx in faixas_planos if fx is not None), None)
        obs = ((fx0.observacao_valor or "").strip() if fx0 else "")
        rotulo_html = html.escape(rotulo_fx)
        if obs:
            rotulo_html += f"<span class='fx-obs'>{html.escape(obs)}</span>"
        partes.append(
            f"<tr><td data-fx='{html.escape(rotulo_fx, quote=True)}'>{rotulo_html}</td>"
        )
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
                    alvos = [
                        pl
                        for secao in model.secoes_regime
                        for pl in secao.planos_atuais
                        if plano is None or pl.subgrupo_id == plano.subgrupo_id
                    ] or planos
                    for pl in alvos:
                        valor = _valor_faixa_prop(_faixa_do_plano(pl, rotulo_fx), oid)
                        if valor is not None:
                            break
                    partes.append(
                        f"<td>{_cel_money(valor)}</td>"
                        if valor is not None
                        else "<td></td>"
                    )
        partes.append("</tr>")

    partes.append("</tbody><tfoot><tr><td>Total</td>")
    partes.append(
        "<td class='col-titdep'></td>"
        "<td class='col-titdep'></td>"
        f"<td class='col-vidas'>{vidas_total}</td>"
    )
    sg = plano.subgrupo_id if plano is not None else None
    atual_c = plano.subtotal_reajustado_centavos if plano is not None else None
    for b in blocos:
        if b.atual:
            reaj_c = (
                (plano.subtotal_reajustado_centavos if plano is not None else None)
                or sum((p.subtotal_reajustado_centavos or 0) for p in b.planos)
                or None
            )
            pct = (
                plano.reajuste_percentual_exibicao
                if plano is not None
                else model.reajuste_consolidado_percentual_exibicao
            )
            partes.append(
                "<td class='atual'>" + _contrato_atual_html(reaj_c, pct) + "</td>"
            )
        else:
            for oid in b.op_ids:
                total = (
                    _subtotal_proposta_todas_secoes(model, sg, oid)
                    if sg
                    else model.totais_gerais.propostas.get(oid)
                )
                partes.append(f"<td>{_cel_money(total)}</td>")
    partes.append("</tr>")
    partes.append(
        _linha_total_parentesco_faixas(
            "Total titular",
            blocos,
            model,
            plano,
            op_ids,
            campo="titular",
            seguro_novo=seguro_novo,
        )
    )
    partes.append(
        _linha_total_parentesco_faixas(
            "Total dependente",
            blocos,
            model,
            plano,
            op_ids,
            campo="dependente",
            seguro_novo=seguro_novo,
        )
    )
    if not seguro_novo and atual_c is not None:
        partes.append("<tr><td>Diferença mensal</td>")
        partes.append(
            "<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>"
        )
        for b in blocos:
            if b.atual:
                partes.append("<td class='atual'>referência</td>")
            else:
                for oid in b.op_ids:
                    prop_c = _subtotal_proposta_todas_secoes(model, sg, oid) if sg else None
                    diff = None if prop_c is None else prop_c - atual_c
                    partes.append(f"<td>{_cel_money(diff, diff=True)}</td>")
        partes.append("</tr><tr><td>Diferença anual</td>")
        partes.append(
            "<td class='col-titdep'></td><td class='col-titdep'></td><td class='col-vidas'></td>"
        )
        for b in blocos:
            if b.atual:
                partes.append(f"<td class='atual'>{_AUSENCIA}</td>")
            else:
                for oid in b.op_ids:
                    prop_c = _subtotal_proposta_todas_secoes(model, sg, oid) if sg else None
                    diff = None if prop_c is None else (prop_c - atual_c) * 12
                    partes.append(f"<td>{_cel_money(diff, diff=True)}</td>")
        partes.append("</tr>")
    partes.append("</tfoot></table></div>")
    return "".join(partes)


def render_tabela_faixas(
    model: PresentationViewModel,
    op_ids: list[str],
    rotulos: dict[str, str],
    *,
    seguro_novo: bool,
) -> str:
    """Documento: uma seção de faixas por grupo, como a tela já faz."""
    planos = planos_das_faixas(model, seguro_novo=seguro_novo)
    if seguro_novo or not planos:
        return render_secao_faixas_grupo(
            model, op_ids, rotulos, None, seguro_novo=seguro_novo
        )
    partes = [
        render_secao_faixas_grupo(
            model, op_ids, rotulos, plano, seguro_novo=False
        )
        for plano in planos
    ]
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
