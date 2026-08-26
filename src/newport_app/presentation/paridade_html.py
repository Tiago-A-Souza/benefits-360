"""Paridade inventário PresentationViewModel ↔ HTML renderizado.

Extrai por parse da árvore HTML (stdlib). Valores monetários por chave
posicional (linha, coluna) — conjunto igual com colunas trocadas falha.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from newport_app.models.presentation import PresentationViewModel
from newport_app.presentation.formatacao import formatar_reais

_PLANO_SINTETICO = "vidas-incluidas"

_RE_REAIS = re.compile(
    r"R\$\s*(-?)\s*((?:\d{1,3}(?:\.\d{3})*|\d+)),(\d{2})"
)


def reais_para_centavos(texto: str) -> int | None:
    m = _RE_REAIS.search(texto.replace("\xa0", " "))
    if not m:
        return None
    sinal = -1 if m.group(1) == "-" else 1
    inteiro = int(m.group(2).replace(".", ""))
    cents = int(m.group(3))
    return sinal * (inteiro * 100 + cents)


def _norm(texto: str) -> str:
    return " ".join(texto.split()).strip()


@dataclass
class InventarioRender:
    secoes: frozenset[str] = field(default_factory=frozenset)
    propostas: frozenset[str] = field(default_factory=frozenset)
    planos: frozenset[str] = field(default_factory=frozenset)
    # Planos que aparecem como linha de tabela de resumo (não só h3 de faixas).
    planos_linha_resumo: frozenset[str] = field(default_factory=frozenset)
    faixas: frozenset[str] = field(default_factory=frozenset)
    vidas: frozenset[str] = field(default_factory=frozenset)
    valores_centavos: frozenset[int] = field(default_factory=frozenset)
    linhas: frozenset[str] = field(default_factory=frozenset)
    colunas: frozenset[str] = field(default_factory=frozenset)
    # (rótulo_linha, rótulo_coluna) → centavos
    celulas_pos: dict[tuple[str, str], int] = field(default_factory=dict)


class _HtmlTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict[str, Any] = {
            "tag": "document",
            "attrs": {},
            "children": [],
            "text": "",
        }
        self._stack: list[dict[str, Any]] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = {
            "tag": tag.lower(),
            "attrs": {k.lower(): (v or "") for k, v in attrs},
            "children": [],
            "text": "",
        }
        self._stack[-1]["children"].append(node)
        if tag.lower() not in {
            "br",
            "hr",
            "img",
            "input",
            "meta",
            "link",
            "area",
            "base",
            "col",
            "embed",
            "source",
            "track",
            "wbr",
        }:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self._stack[-1]["text"] += data


def parse_html_tree(html_doc: str) -> dict[str, Any]:
    parser = _HtmlTreeParser()
    parser.feed(html_doc)
    parser.close()
    return parser.root


def _texto(node: dict[str, Any]) -> str:
    partes = [node.get("text") or ""]
    for ch in node.get("children") or []:
        partes.append(_texto(ch))
    return _norm("".join(partes))


def _iter(node: dict[str, Any], tag: str | None = None):
    if tag is None or node.get("tag") == tag:
        yield node
    for ch in node.get("children") or []:
        yield from _iter(ch, tag)


def _attr_class(node: dict[str, Any]) -> set[str]:
    return set((node.get("attrs") or {}).get("class", "").split())


def _filhos(node: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    return [c for c in (node.get("children") or []) if c.get("tag") == tag]


def _celulas_linha(tr: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in (tr.get("children") or []) if c.get("tag") in {"td", "th"}]


def _colspan(cell: dict[str, Any]) -> int:
    raw = (cell.get("attrs") or {}).get("colspan") or "1"
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def _rotulo_coluna(th: dict[str, Any]) -> str:
    for span in _iter(th, "span"):
        if "op" in _attr_class(span):
            t = _texto(span)
            if t:
                return t
    return _texto(th)


def _expandir_cabecalho(tr: dict[str, Any]) -> list[str]:
    """Uma entrada por coluna visual (respeita colspan)."""
    cols: list[str] = []
    for th in _celulas_linha(tr):
        rotulo = _rotulo_coluna(th)
        for _ in range(_colspan(th)):
            cols.append(rotulo)
    return cols


def _escopo_raiz(root: dict[str, Any], secao_id: str | None) -> dict[str, Any]:
    if not secao_id:
        return root
    for node in _iter(root):
        if (node.get("attrs") or {}).get("id") == secao_id:
            return node
    return root


def inventariar_html(
    html_doc: str, *, secao_id: str | None = None
) -> InventarioRender:
    root = _escopo_raiz(parse_html_tree(html_doc), secao_id)
    secoes: set[str] = set()
    propostas: set[str] = set()
    planos: set[str] = set()
    planos_linha: set[str] = set()
    faixas: set[str] = set()
    vidas: set[str] = set()
    valores: set[int] = set()
    linhas: set[str] = set()
    colunas: set[str] = set()
    celulas_pos: dict[tuple[str, str], int] = {}

    for node in _iter(root):
        classes = _attr_class(node)
        tag = node.get("tag")
        if tag == "section" and "secao-regime" in classes:
            for h2 in _iter(node, "h2"):
                t = _texto(h2)
                if t and "visao-titulo" not in _attr_class(h2):
                    secoes.add(t)
                    break
        if tag == "h3":
            t = _texto(node)
            if t.startswith("Plano atual —"):
                resto = t.split("—", 1)[-1].strip()
                nome = (
                    _norm(resto.split("·", 1)[-1]) if "·" in resto else _norm(resto)
                )
                planos.add(nome)
        if tag == "span" and "op" in classes:
            t = _texto(node)
            if t and t not in {"Contrato atual"}:
                propostas.add(t)
                colunas.add(t)
        if "rv" in classes and tag == "span":
            cent = reais_para_centavos(_texto(node))
            if cent is not None:
                valores.add(cent)

    for table in _iter(root, "table"):
        cab: list[str] = []
        for thead in _filhos(table, "thead"):
            for tr in _filhos(thead, "tr"):
                cab = _expandir_cabecalho(tr)
                for th in _celulas_linha(tr):
                    t = _rotulo_coluna(th)
                    if t:
                        colunas.add(t)
                        if t != "Contrato atual":
                            for span in _iter(th, "span"):
                                if "op" in _attr_class(span) and _texto(span):
                                    propostas.add(_texto(span))
                break
            if cab:
                break
        primeiro_th = cab[0] if cab else ""

        for corpo in _filhos(table, "tbody") + _filhos(table, "tfoot"):
            for tr in _filhos(corpo, "tr"):
                cells = _celulas_linha(tr)
                if not cells:
                    continue
                rotulo = _texto(cells[0])
                if rotulo:
                    linhas.add(rotulo)
                # Expande células do body conforme colspan para alinhar ao cab.
                slots: list[tuple[str, dict[str, Any]]] = []
                for cell in cells:
                    for _ in range(_colspan(cell)):
                        slots.append((_texto(cell), cell))
                if not cab:
                    for _txt, cell in slots:
                        cent = reais_para_centavos(_texto(cell))
                        if cent is not None:
                            valores.add(cent)
                    continue
                # Alinha: slots[0] = rótulo da linha; demais batem com cab[1:]…
                # Se lengths differ, zip until min.
                for idx in range(1, min(len(slots), len(cab))):
                    col_rotulo = cab[idx]
                    cell = slots[idx][1]
                    cent = reais_para_centavos(_texto(cell))
                    if cent is None:
                        continue
                    valores.add(cent)
                    if not rotulo or not col_rotulo:
                        continue
                    # Em faixas, 3 colunas por proposta (unit/qtd/subtotal):
                    # grava a última ocorrência (subtotal) para (linha, proposta).
                    celulas_pos[(rotulo, col_rotulo)] = cent

        if primeiro_th == "Faixa":
            for tbody in _filhos(table, "tbody"):
                for tr in _filhos(tbody, "tr"):
                    cells = _celulas_linha(tr)
                    if cells:
                        faixas.add(_texto(cells[0]))
        elif primeiro_th in {"Beneficiário", "Nome"}:
            for tbody in _filhos(table, "tbody"):
                for tr in _filhos(tbody, "tr"):
                    cells = _celulas_linha(tr)
                    if cells:
                        vidas.add(_texto(cells[0]))
        elif primeiro_th == "Proposta":
            for tbody in _filhos(table, "tbody"):
                for tr in _filhos(tbody, "tr"):
                    cells = _celulas_linha(tr)
                    if cells and _texto(cells[0]):
                        propostas.add(_texto(cells[0]))
        elif primeiro_th == "Indicador":
            for tbody in _filhos(table, "tbody"):
                for tr in _filhos(tbody, "tr"):
                    cells = _celulas_linha(tr)
                    if not cells:
                        continue
                    rotulo = _texto(cells[0])
                    if (
                        rotulo
                        and not rotulo.startswith("Diferença")
                        and rotulo != "Consolidado"
                    ):
                        planos.add(rotulo)
                        planos_linha.add(rotulo)

    return InventarioRender(
        secoes=frozenset(secoes),
        propostas=frozenset(propostas),
        planos=frozenset(planos),
        planos_linha_resumo=frozenset(planos_linha),
        faixas=frozenset(faixas),
        vidas=frozenset(vidas),
        valores_centavos=frozenset(valores),
        linhas=frozenset(linhas),
        colunas=frozenset(colunas),
        celulas_pos=celulas_pos,
    )


def _centavos_recursivo(obj: Any, acc: set[int]) -> None:
    if obj is None:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.endswith("_centavos") and isinstance(v, int):
                acc.add(v)
                acc.add(abs(v))
            _centavos_recursivo(v, acc)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _centavos_recursivo(item, acc)
        return
    if hasattr(obj, "model_dump"):
        dados = obj.model_dump()
        for chave in ("propostas", "diff_mensal", "diff_anual"):
            mapa = dados.get(chave)
            if isinstance(mapa, dict):
                for v in mapa.values():
                    if isinstance(v, int):
                        acc.add(v)
                        acc.add(abs(v))
        _centavos_recursivo(dados, acc)


def _valores_derivados_vm(vm: PresentationViewModel) -> set[int]:
    acc: set[int] = set()
    tg = vm.totais_gerais
    if tg.atual_centavos is not None:
        acc.add(tg.atual_centavos * 12)
    totais = [v for v in tg.propostas.values() if isinstance(v, int)]
    if len(totais) >= 2:
        menor = min(totais)
        for t in totais:
            acc.add(t - menor)
            acc.add(abs(t - menor))
    for secao in vm.secoes_regime:
        st = [v for v in secao.totais.propostas.values() if isinstance(v, int)]
        if len(st) >= 2:
            menor = min(st)
            for t in st:
                acc.add(t - menor)
                acc.add(abs(t - menor))
        for pl in secao.planos_atuais:
            for op_id in vm.propostas_selecionadas:
                sub = sum(
                    col.subtotal_centavos or 0
                    for fx in pl.faixas
                    for col in fx.propostas
                    if col.opcao_id == op_id
                )
                if sub:
                    acc.add(sub)
    return acc


def _subtotal_plano_prop(plano, op_id: str) -> int | None:
    vals = [
        col.subtotal_centavos
        for fx in plano.faixas
        for col in fx.propostas
        if col.opcao_id == op_id and col.subtotal_centavos is not None
    ]
    if not vals:
        return None
    return sum(vals)


def celulas_posicionais_vm(vm: PresentationViewModel) -> dict[tuple[str, str], int]:
    """Chaves (rótulo_linha, rótulo_coluna) espelhando o que o HTML deve mostrar."""
    cells: dict[tuple[str, str], int] = {}

    if vm.modo == "resumo":
        for secao in vm.secoes_regime:
            props = list(secao.propostas)
            if vm.formato == "novo":
                for prop in props:
                    total = secao.totais.propostas.get(prop.opcao_id)
                    if total is None:
                        total = prop.total_mensal_centavos
                    if isinstance(total, int):
                        cells[(prop.plano_nome, "Total mensal")] = total
                    diff_m = secao.totais.diff_mensal.get(prop.opcao_id)
                    if diff_m is None:
                        diff_m = prop.diff_mensal_centavos
                    if isinstance(diff_m, int) and diff_m != 0:
                        cells[(prop.plano_nome, "Diferença vs menor (mês)")] = diff_m
                    diff_a = secao.totais.diff_anual.get(prop.opcao_id)
                    if diff_a is None:
                        diff_a = prop.diff_anual_centavos
                    if isinstance(diff_a, int) and diff_a != 0:
                        cells[(prop.plano_nome, "Diferença vs menor (ano)")] = diff_a
                continue
            for pl in secao.planos_atuais:
                if pl.subgrupo_id == _PLANO_SINTETICO:
                    continue
                if pl.subtotal_reajustado_centavos is not None:
                    cells[(pl.plano_nome, "Contrato atual")] = (
                        pl.subtotal_reajustado_centavos
                    )
                for prop in props:
                    sub = _subtotal_plano_prop(pl, prop.opcao_id)
                    if sub is not None:
                        cells[(pl.plano_nome, prop.plano_nome)] = sub
        return cells

    if vm.modo == "faixas":
        for secao in vm.secoes_regime:
            props = list(secao.propostas)
            for pl in secao.planos_atuais:
                for fx in pl.faixas:
                    for prop in props:
                        col = next(
                            (c for c in fx.propostas if c.opcao_id == prop.opcao_id),
                            None,
                        )
                        if col and col.subtotal_centavos is not None:
                            # Várias tabelas (um plano cada) reutilizam o rótulo de faixa;
                            # a última ocorrência espelha o inventário HTML agregado.
                            cells[(fx.rotulo, prop.plano_nome)] = col.subtotal_centavos
        return cells

    if vm.modo == "beneficiario":
        prop_por_id = {
            p.opcao_id: p.plano_nome
            for s in vm.secoes_regime
            for p in s.propostas
        }
        for b in vm.beneficiarios:
            if b.atual_reajustado_centavos is not None:
                cells[(b.nome, "Contrato atual")] = b.atual_reajustado_centavos
            for col in b.propostas:
                if col.valor_centavos is None:
                    continue
                nome = prop_por_id.get(col.opcao_id, col.opcao_id)
                cells[(b.nome, nome)] = col.valor_centavos
        return cells

    return cells


def inventariar_vm(vm: PresentationViewModel) -> InventarioRender:
    secoes: set[str] = set()
    propostas: set[str] = set()
    planos: set[str] = set()
    faixas: set[str] = set()
    vidas: set[str] = set()
    valores: set[int] = set()

    for secao in vm.secoes_regime:
        if secao.regime_rotulo:
            secoes.add(secao.regime_rotulo)
            secoes.add(f"Resumo executivo — {secao.regime_rotulo}")
        for prop in secao.propostas:
            propostas.add(prop.plano_nome)
        for pl in secao.planos_atuais:
            if pl.subgrupo_id != _PLANO_SINTETICO:
                planos.add(pl.plano_nome)
            for fx in pl.faixas:
                faixas.add(fx.rotulo)

    for b in vm.beneficiarios:
        vidas.add(b.nome)

    _centavos_recursivo(vm, valores)
    valores |= _valores_derivados_vm(vm)
    celulas_pos = celulas_posicionais_vm(vm)

    return InventarioRender(
        secoes=frozenset(secoes),
        propostas=frozenset(propostas),
        planos=frozenset(planos),
        planos_linha_resumo=frozenset(planos),
        faixas=frozenset(faixas),
        vidas=frozenset(vidas),
        valores_centavos=frozenset(valores),
        celulas_pos=celulas_pos,
    )


def valores_principais_vm(vm: PresentationViewModel) -> frozenset[int]:
    vals = {v for v in vm.totais_gerais.propostas.values() if isinstance(v, int)}
    for secao in vm.secoes_regime:
        for v in secao.totais.propostas.values():
            if isinstance(v, int):
                vals.add(v)
    return frozenset(vals)


def divergencias_celulas_pos(
    modelo: dict[tuple[str, str], int],
    html: dict[tuple[str, str], int],
    *,
    prefixo: str = "",
) -> list[str]:
    """Compara centavos por (linha, coluna). Conjunto igual com posições trocadas falha."""
    divs: list[str] = []
    comuns = set(modelo) & set(html)
    n_trocadas = 0
    for chave in sorted(comuns):
        if modelo[chave] != html[chave]:
            n_trocadas += 1
            divs.append(
                f"{prefixo}célula pos {chave}: "
                f"modelo={formatar_reais(modelo[chave])} "
                f"html={formatar_reais(html[chave])}"
            )
    so_m = sorted(set(modelo) - set(html))
    if so_m:
        divs.append(
            f"{prefixo}células posicionais só no modelo ({len(so_m)}): "
            + ", ".join(repr(c) for c in so_m[:8])
            + ("…" if len(so_m) > 8 else "")
        )
    if n_trocadas:
        divs.insert(
            0,
            f"{prefixo}células posicionais com valor trocado/errado: {n_trocadas}",
        )
    return divs


def divergencias_html_vm(vm: PresentationViewModel, html_doc: str) -> list[str]:
    iv = inventariar_vm(vm)
    ih = inventariar_html(html_doc)
    valores_modelo = set(iv.valores_centavos) | {0}
    divs: list[str] = []

    def _faltando(nome: str, modelo: frozenset[str], html_set: frozenset[str]) -> None:
        falta = sorted(modelo - html_set)
        if falta:
            divs.append(
                f"{nome} no modelo ausentes no HTML ({len(falta)}): {falta}"
                + (f" | html_tem={sorted(html_set)}" if html_set else " | html_vazio")
            )

    _faltando("propostas", iv.propostas, ih.propostas)

    if vm.modo == "resumo":
        # Linhas de plano no resumo — não vale h3 da visão faixas.
        _faltando("planos", iv.planos, ih.planos_linha_resumo or ih.planos)
    elif vm.modo == "faixas":
        _faltando("planos", iv.planos, ih.planos)

    if vm.modo == "faixas":
        _faltando("faixas", iv.faixas, ih.faixas)
        if iv.faixas and len(ih.faixas) < len(iv.faixas):
            divs.append(
                f"contagem faixas: modelo={len(iv.faixas)} html={len(ih.faixas)} "
                f"linhas_tabela={len(ih.linhas)}"
            )
    if vm.modo == "beneficiario":
        _faltando("vidas", iv.vidas, ih.vidas)

    if vm.modo in {"resumo", "faixas"}:
        principais = valores_principais_vm(vm)
        principais_ausentes = sorted(principais - ih.valores_centavos)
        if principais_ausentes:
            divs.append(
                f"valores principais ausentes no HTML ({len(principais_ausentes)}): "
                + ", ".join(formatar_reais(c) for c in principais_ausentes[:8])
                + ("…" if len(principais_ausentes) > 8 else "")
            )

    if vm.modo == "resumo" and not iv.planos and iv.propostas:
        falta_linhas = sorted(iv.propostas - ih.linhas - ih.propostas)
        if falta_linhas:
            divs.append(
                f"resumo sem linhas de proposta do modelo: ausentes={falta_linhas} "
                f"html_linhas={sorted(ih.linhas)}"
            )

    # Posicional: valores em comum com chave (linha, coluna) devem coincidir.
    divs.extend(divergencias_celulas_pos(iv.celulas_pos, ih.celulas_pos))

    inventados = sorted(ih.valores_centavos - valores_modelo)
    if inventados:
        amostra = inventados[:8]
        divs.append(
            f"valores no HTML ausentes do modelo ({len(inventados)}): "
            + ", ".join(formatar_reais(c) for c in amostra)
            + ("…" if len(inventados) > 8 else "")
        )

    return divs


def assert_paridade_html_vm(vm: PresentationViewModel, html_doc: str) -> None:
    divs = divergencias_html_vm(vm, html_doc)
    assert not divs, "paridade HTML↔VM falhou:\n- " + "\n- ".join(divs)
