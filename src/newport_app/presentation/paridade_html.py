"""Paridade inventário PresentationViewModel ↔ HTML renderizado (fase 1, camada 2).

Extrai estrutura e valores monetários por parse da árvore HTML (stdlib),
sem lista de linhas esperadas escrita à mão.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

from newport_app.models.presentation import PresentationViewModel
from newport_app.presentation.formatacao import formatar_reais

_PLANO_SINTETICO = "vidas-incluidas"

# R$ -1.234,56 ou R$ 1.234,56 (espaços opcionais)
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
    """Inventário do que o modelo declara ou o HTML efetivamente mostra."""

    secoes: frozenset[str] = field(default_factory=frozenset)
    propostas: frozenset[str] = field(default_factory=frozenset)  # rótulos (plano_nome)
    planos: frozenset[str] = field(default_factory=frozenset)  # nomes de plano real
    faixas: frozenset[str] = field(default_factory=frozenset)  # rótulos de faixa
    vidas: frozenset[str] = field(default_factory=frozenset)  # nomes / rótulos de vida
    valores_centavos: frozenset[int] = field(default_factory=frozenset)
    # Linhas de tabela (1ª célula), para diagnóstico de contagem.
    linhas: frozenset[str] = field(default_factory=frozenset)
    colunas: frozenset[str] = field(default_factory=frozenset)


class _HtmlTreeParser(HTMLParser):
    """Constrói árvore mínima (tag, attrs, children, text)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: dict[str, Any] = {"tag": "document", "attrs": {}, "children": [], "text": ""}
        self._stack: list[dict[str, Any]] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = {
            "tag": tag.lower(),
            "attrs": {k.lower(): (v or "") for k, v in attrs},
            "children": [],
            "text": "",
        }
        self._stack[-1]["children"].append(node)
        # void-ish: não empilhar
        if tag.lower() not in {
            "br", "hr", "img", "input", "meta", "link", "area", "base",
            "col", "embed", "source", "track", "wbr",
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
    out: list[dict[str, Any]] = []
    for ch in tr.get("children") or []:
        if ch.get("tag") in {"td", "th"}:
            out.append(ch)
    return out


def inventariar_html(html_doc: str) -> InventarioRender:
    root = parse_html_tree(html_doc)
    secoes: set[str] = set()
    propostas: set[str] = set()
    planos: set[str] = set()
    faixas: set[str] = set()
    vidas: set[str] = set()
    valores: set[int] = set()
    linhas: set[str] = set()
    colunas: set[str] = set()

    for node in _iter(root):
        classes = _attr_class(node)
        tag = node.get("tag")

        if tag == "section" and "secao-regime" in classes:
            # h2 imediato / primeiro h2
            for h2 in _iter(node, "h2"):
                t = _texto(h2)
                if t and "visao-titulo" not in _attr_class(h2):
                    secoes.add(t)
                    break

        if tag == "h3":
            t = _texto(node)
            if t.startswith("Plano atual —"):
                # "Plano atual — Op · Nome"
                resto = t.split("—", 1)[-1].strip()
                if "·" in resto:
                    planos.add(_norm(resto.split("·", 1)[-1]))
                else:
                    planos.add(_norm(resto))

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
        theads = _filhos(table, "thead")
        for thead in theads:
            for tr in _filhos(thead, "tr"):
                for th in _celulas_linha(tr):
                    t = _texto(th)
                    if t:
                        colunas.add(t)
                        for span in _iter(th, "span"):
                            if "op" in _attr_class(span):
                                nome = _texto(span)
                                if nome and nome != "Contrato atual":
                                    propostas.add(nome)

        corpos = _filhos(table, "tbody") + _filhos(table, "tfoot")
        for corpo in corpos:
            for tr in _filhos(corpo, "tr"):
                cells = _celulas_linha(tr)
                if not cells:
                    continue
                rotulo = _texto(cells[0])
                if rotulo:
                    linhas.add(rotulo)
                for cell in cells:
                    cent = reais_para_centavos(_texto(cell))
                    if cent is not None:
                        valores.add(cent)

    # Classifica linhas: se o rótulo coincide com faixa conhecida no texto
    # (faixas ANS típicas / qualquer linha que não é indicador fixo óbvio).
    # Sem lista de indicadores: faixas = linhas que o VM declarar — a classificação
    # fina fica na comparação. Aqui guardamos todas as linhas.
    # Planos: linhas cujo texto está em h3 ou bate com plano do cabeçalho de resumo.
    # Heurística mínima: linhas de tabela em seção com h3 de plano alimentam faixas
    # quando a 1ª coluna não é só quantidade.
    for table in _iter(root, "table"):
        # Só a 1ª coluna do thead define o tipo da linha (evita th «Faixa» no meio).
        primeiro_th = ""
        for thead in _filhos(table, "thead"):
            for tr in _filhos(thead, "tr"):
                cells = _celulas_linha(tr)
                if cells:
                    primeiro_th = _texto(cells[0])
                    break
            if primeiro_th:
                break

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
                    # Plano atual como texto de célula (não é linha-entidade).
                    for cell in cells[1:]:
                        t = _texto(cell)
                        if t and not _RE_REAIS.search(t) and t not in {"", "—"}:
                            # Heurística frouxa demais — planos no benef. via match no assert.
                            pass
        elif primeiro_th == "Indicador":
            for tbody in _filhos(table, "tbody"):
                for tr in _filhos(tbody, "tr"):
                    cells = _celulas_linha(tr)
                    if not cells:
                        continue
                    rotulo = _texto(cells[0])
                    if rotulo and not rotulo.startswith("Diferença") and rotulo != "Consolidado":
                        planos.add(rotulo)

    return InventarioRender(
        secoes=frozenset(secoes),
        propostas=frozenset(propostas),
        planos=frozenset(planos),
        faixas=frozenset(faixas),
        vidas=frozenset(vidas),
        valores_centavos=frozenset(valores),
        linhas=frozenset(linhas),
        colunas=frozenset(colunas),
    )


def _centavos_recursivo(obj: Any, acc: set[int]) -> None:
    if obj is None:
        return
    if isinstance(obj, int):
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.endswith("_centavos") and isinstance(v, int):
                acc.add(v)
                acc.add(abs(v))
            elif isinstance(v, int) and k in {"propostas", "diff_mensal", "diff_anual"}:
                # dict values handled below
                pass
            _centavos_recursivo(v, acc)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            _centavos_recursivo(item, acc)
        return
    if hasattr(obj, "model_dump"):
        dados = obj.model_dump()
        # Totais: dict[str, int|None]
        for chave in ("propostas", "diff_mensal", "diff_anual"):
            mapa = dados.get(chave)
            if isinstance(mapa, dict):
                for v in mapa.values():
                    if isinstance(v, int):
                        acc.add(v)
                        acc.add(abs(v))
        _centavos_recursivo(dados, acc)


def _valores_derivados_vm(vm: PresentationViewModel) -> set[int]:
    """Valores que o renderer pode sintetizar a partir do VM (ainda «do modelo»)."""
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


def inventariar_vm(vm: PresentationViewModel) -> InventarioRender:
    secoes: set[str] = set()
    propostas: set[str] = set()
    planos: set[str] = set()
    faixas: set[str] = set()
    vidas: set[str] = set()
    valores: set[int] = set()

    for secao in vm.secoes_regime:
        if secao.regime_rotulo:
            # HTML: "Resumo executivo — {rotulo}" ou só rotulo no h2 de faixas
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

    return InventarioRender(
        secoes=frozenset(secoes),
        propostas=frozenset(propostas),
        planos=frozenset(planos),
        faixas=frozenset(faixas),
        vidas=frozenset(vidas),
        valores_centavos=frozenset(valores),
    )


def valores_principais_vm(vm: PresentationViewModel) -> frozenset[int]:
    """Totais mensais por proposta — não podem sumir em nenhuma visão."""
    vals = {v for v in vm.totais_gerais.propostas.values() if isinstance(v, int)}
    for secao in vm.secoes_regime:
        for v in secao.totais.propostas.values():
            if isinstance(v, int):
                vals.add(v)
    return frozenset(vals)


def divergencias_html_vm(vm: PresentationViewModel, html_doc: str) -> list[str]:
    """Modelo → HTML (o que a visão comporta) e HTML → modelo (valores inventados).

    Entidades por visão (sem lista de indicadores):
    - resumo: propostas + planos reais; faixas NÃO exigidas aqui (decisão de produto)
    - faixas: propostas + planos reais + faixas
    - beneficiario: propostas + vidas

    Valores principais (totais mensais por proposta) em resumo e faixas —
    se o resumo renderiza 1 linha e omite o total, falha.
    """
    iv = inventariar_vm(vm)
    ih = inventariar_html(html_doc)
    # 0 pode aparecer como diferença nula no HTML.
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

    if vm.modo in {"resumo", "faixas"}:
        _faltando("planos", iv.planos, ih.planos)
    if vm.modo == "faixas":
        _faltando("faixas", iv.faixas, ih.faixas)
        # Diagnóstico explícito da classe «N faixas no modelo × M linhas na visão».
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

    # Se o resumo não tem planos reais, as faixas do VM são a estrutura de linha
    # disponível — omiti-las no HTML é descarte (classe N faixas × 1 linha).
    if vm.modo == "resumo" and not iv.planos and iv.faixas and not ih.faixas:
        divs.append(
            f"resumo sem estrutura de faixas do modelo: modelo_faixas={sorted(iv.faixas)} "
            f"html_linhas={len(ih.linhas)} ({sorted(ih.linhas)})"
        )

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
