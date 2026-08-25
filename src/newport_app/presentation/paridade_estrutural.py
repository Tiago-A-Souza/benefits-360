"""Paridade estrutural ComparativoResponse ↔ PresentationViewModel (fase 1).

Compara conjuntos e células monetárias descobertas — sem lista fixa de
indicadores de UI. Não lê HTML/DOM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from newport_app.models.presentation import PresentationViewModel
from newport_app.models.responses import ComparativoResponse

# Plano sintético do VM em seguro novo — fora do conjunto de planos.
_PLANO_SINTETICO = "vidas-incluidas"
_ESTUDO = "__estudo__"

# Normaliza nomes de métrica para a chave canônica (matriz ↔ VM).
_ALIAS_METRICA: dict[str, str] = {
    "vigente_centavos": "vigente",
    "subtotal_vigente_centavos": "vigente",
    "reajustado_centavos": "reajustado",
    "subtotal_reajustado_centavos": "reajustado",
    "mensal_centavos": "mensal",
    "atual_mensal_centavos": "atual_mensal",
    "proposta_mensal_centavos": "proposta_mensal",
    "total_mensal_centavos": "proposta_mensal",
    "diff_mes_centavos": "diff_mes",
    "diff_mensal_centavos": "diff_mes",
    "diff_ano_centavos": "diff_ano",
    "diff_anual_centavos": "diff_ano",
    "proposta_centavos": "proposta",
    "unitario_centavos": "unitario",
    "valor_unitario_centavos": "unitario",
    "subtotal_centavos": "subtotal",
    "vigente_unitario_centavos": "vigente_unitario",
    "atual_vigente_unitario_centavos": "vigente_unitario",
    "vigente_total_centavos": "vigente_total",
    "atual_vigente_total_centavos": "vigente_total",
    "reajustado_unitario_centavos": "reajustado_unitario",
    "atual_reajustado_unitario_centavos": "reajustado_unitario",
    "reajustado_total_centavos": "reajustado_total",
    "atual_reajustado_total_centavos": "reajustado_total",
    "atual_centavos": "atual",
    "atual_reajustado_centavos": "reajustado",
    "atual_vigente_centavos": "vigente",
    "diff_centavos": "diff_mes",
    "premio_centavos": "premio",
    "iof_centavos": "iof",
    "total_recorrente_centavos": "total_recorrente",
    "valor_centavos": "proposta",
}


def _canon(nome: str) -> str | None:
    return _ALIAS_METRICA.get(nome)


def _plano_key(subgrupo_id: str) -> str:
    if subgrupo_id == _PLANO_SINTETICO:
        return _ESTUDO
    return subgrupo_id


@dataclass
class EstruturaApresentacao:
    propostas: frozenset[str] = field(default_factory=frozenset)
    planos: frozenset[str] = field(default_factory=frozenset)
    regimes: frozenset[str] = field(default_factory=frozenset)
    faixas: frozenset[tuple[str, int]] = field(default_factory=frozenset)
    vidas: frozenset[str] = field(default_factory=frozenset)
    celulas: dict[tuple[Any, ...], int | None] = field(default_factory=dict)


def _put(celulas: dict[tuple[Any, ...], int | None], chave: tuple[Any, ...], valor: int | None) -> None:
    if chave in celulas and celulas[chave] != valor:
        # Mantém o primeiro; divergência interna será vista se o outro lado diferir.
        return
    celulas[chave] = valor


def _centavos_de_modelo(obj: Any, celulas: dict[tuple[Any, ...], int | None], prefixo: tuple[Any, ...]) -> None:
    """Descobre campos *_centavos no modelo (Pydantic ou dict) e grava células."""
    if obj is None:
        return
    dados = obj.model_dump() if hasattr(obj, "model_dump") else obj
    if not isinstance(dados, dict):
        return
    for nome, valor in dados.items():
        if not nome.endswith("_centavos"):
            continue
        metrica = _canon(nome)
        if metrica is None:
            # Métrica sem alias conhecido: usa o nome sem sufixo (ainda descoberta).
            metrica = nome[: -len("_centavos")]
        if isinstance(valor, int):
            _put(celulas, prefixo + (metrica,), valor)
        # None = campo ausente — não gera célula (evita ruído de dump).


def extrair_estrutura_matriz(matriz: ComparativoResponse) -> EstruturaApresentacao:
    propostas = frozenset(
        p.opcao_id for p in matriz.propostas if p.calculo_realizado
    )
    planos = frozenset(p.subgrupo_id for p in matriz.planos_atuais)
    regimes = frozenset(p.regime_tipo for p in matriz.propostas if p.calculo_realizado)
    faixas: set[tuple[str, int]] = set()
    vidas: set[str] = set()
    celulas: dict[tuple[Any, ...], int | None] = {}

    for pl in matriz.planos_atuais:
        pk = _plano_key(pl.subgrupo_id)
        _centavos_de_modelo(pl, celulas, ("plano", pk))
        for fx in pl.faixas:
            faixas.add((pk, fx.faixa))
            _centavos_de_modelo(fx, celulas, ("faixa", pk, fx.faixa))
            for col in fx.propostas:
                _centavos_de_modelo(
                    col, celulas, ("faixa_prop", pk, fx.faixa, col.opcao_id)
                )

    if matriz.formato == "novo" or not matriz.planos_atuais:
        for fx in matriz.faixas_estudo or []:
            faixas.add((_ESTUDO, fx.faixa))
            _centavos_de_modelo(fx, celulas, ("faixa", _ESTUDO, fx.faixa))
            for col in fx.propostas:
                _centavos_de_modelo(
                    col, celulas, ("faixa_prop", _ESTUDO, fx.faixa, col.opcao_id)
                )

    for prop in matriz.propostas:
        if not prop.calculo_realizado:
            continue
        if prop.numerico is not None:
            _centavos_de_modelo(prop.numerico, celulas, ("prop", prop.opcao_id))
        for sg in prop.subgrupos:
            _centavos_de_modelo(
                sg, celulas, ("prop_sg", prop.opcao_id, _plano_key(sg.subgrupo_id))
            )
        for fx in prop.faixas:
            _centavos_de_modelo(fx, celulas, ("prop_faixa", prop.opcao_id, fx.faixa))
        for sec in prop.secoes:
            for v in sec.vidas:
                vidas.add(v.vida_id)
                _centavos_de_modelo(v, celulas, ("vida", prop.opcao_id, v.vida_id))

    return EstruturaApresentacao(
        propostas=propostas,
        planos=planos,
        regimes=regimes,
        faixas=frozenset(faixas),
        vidas=frozenset(vidas),
        celulas=celulas,
    )


def extrair_estrutura_vm(vm: PresentationViewModel) -> EstruturaApresentacao:
    propostas = frozenset(vm.propostas_selecionadas)
    planos: set[str] = set()
    regimes = frozenset(s.regime_tipo for s in vm.secoes_regime)
    faixas: set[tuple[str, int]] = set()
    vidas = frozenset(b.vida_id for b in vm.beneficiarios)
    celulas: dict[tuple[Any, ...], int | None] = {}

    for secao in vm.secoes_regime:
        for pl in secao.planos_atuais:
            pk = _plano_key(pl.subgrupo_id)
            if pl.subgrupo_id != _PLANO_SINTETICO:
                planos.add(pl.subgrupo_id)
            _centavos_de_modelo(pl, celulas, ("plano", pk))
            for fx in pl.faixas:
                faixas.add((pk, fx.faixa))
                _centavos_de_modelo(fx, celulas, ("faixa", pk, fx.faixa))
                for col in fx.propostas:
                    _centavos_de_modelo(
                        col, celulas, ("faixa_prop", pk, fx.faixa, col.opcao_id)
                    )
        for prop in secao.propostas:
            _centavos_de_modelo(prop, celulas, ("prop", prop.opcao_id))
            # Totais da seção por proposta
            if prop.opcao_id in secao.totais.propostas:
                _put(
                    celulas,
                    ("prop", prop.opcao_id, "proposta_mensal"),
                    secao.totais.propostas.get(prop.opcao_id),
                )
            if prop.opcao_id in secao.totais.diff_mensal:
                _put(
                    celulas,
                    ("prop", prop.opcao_id, "diff_mes"),
                    secao.totais.diff_mensal.get(prop.opcao_id),
                )
            if prop.opcao_id in secao.totais.diff_anual:
                _put(
                    celulas,
                    ("prop", prop.opcao_id, "diff_ano"),
                    secao.totais.diff_anual.get(prop.opcao_id),
                )

    tg = vm.totais_gerais
    if tg.atual_centavos is not None:
        _put(celulas, ("totais", "atual_mensal"), tg.atual_centavos)
    for op_id, val in tg.propostas.items():
        _put(celulas, ("prop", op_id, "proposta_mensal"), val)
    for op_id, val in tg.diff_mensal.items():
        _put(celulas, ("prop", op_id, "diff_mes"), val)
    for op_id, val in tg.diff_anual.items():
        _put(celulas, ("prop", op_id, "diff_ano"), val)

    for b in vm.beneficiarios:
        for col in b.propostas:
            _centavos_de_modelo(col, celulas, ("vida", col.opcao_id, b.vida_id))
        _centavos_de_modelo(b, celulas, ("vida_atual", b.vida_id))

    # Totais por subgrupo derivados das faixas (espelha RecorteSubgrupoComparativo).
    agg: dict[tuple[str, str], int] = {}
    for chave, valor in list(celulas.items()):
        if (
            len(chave) == 5
            and chave[0] == "faixa_prop"
            and chave[4] == "subtotal"
            and isinstance(valor, int)
        ):
            _pk, _fx, op = chave[1], chave[2], chave[3]
            if _pk == _ESTUDO:
                continue
            slot = agg.setdefault((op, _pk), 0)
            agg[(op, _pk)] = slot + valor
    for (op, pk), total in agg.items():
        _put(celulas, ("prop_sg", op, pk, "proposta"), total)

    # Restringe propostas ao que de fato aparece nas seções (interseção).
    ids_secoes = {
        p.opcao_id for s in vm.secoes_regime for p in s.propostas
    }
    if ids_secoes:
        propostas = frozenset(propostas & ids_secoes) if propostas else frozenset(ids_secoes)

    return EstruturaApresentacao(
        propostas=propostas,
        planos=frozenset(planos),
        regimes=regimes,
        faixas=frozenset(faixas),
        vidas=vidas,
        celulas=celulas,
    )


def divergencias_estruturais(
    matriz: ComparativoResponse,
    vm: PresentationViewModel,
    *,
    exigir_vidas: bool | None = None,
) -> list[str]:
    """Lista divergências; lista vazia = paridade estrutural."""
    em = extrair_estrutura_matriz(matriz)
    ev = extrair_estrutura_vm(vm)
    if exigir_vidas is None:
        exigir_vidas = vm.modo == "beneficiario" or bool(vm.beneficiarios)

    divs: list[str] = []

    def _cmp_set(nome: str, a: frozenset, b: frozenset) -> None:
        if a == b:
            return
        so_matriz = sorted(a - b)
        so_vm = sorted(b - a)
        divs.append(
            f"{nome}: matriz={sorted(a)} vm={sorted(b)}"
            + (f" só_matriz={so_matriz}" if so_matriz else "")
            + (f" só_vm={so_vm}" if so_vm else "")
        )

    _cmp_set("propostas", em.propostas, ev.propostas)
    _cmp_set("planos", em.planos, ev.planos)
    _cmp_set("regimes", em.regimes, ev.regimes)
    _cmp_set("faixas", em.faixas, ev.faixas)
    if exigir_vidas:
        _cmp_set("vidas", em.vidas, ev.vidas)

    # Parte E: só valores nas chaves comuns (assimetrías de schema não são defeito).
    comuns = set(em.celulas) & set(ev.celulas)
    if not exigir_vidas:
        comuns = {c for c in comuns if not c or c[0] not in {"vida", "vida_atual"}}
    for chave in sorted(comuns, key=repr):
        if em.celulas[chave] != ev.celulas[chave]:
            divs.append(
                f"célula {chave}: matriz={em.celulas[chave]} vm={ev.celulas[chave]}"
            )

    return divs


def assert_paridade_estrutural(
    matriz: ComparativoResponse,
    vm: PresentationViewModel,
    *,
    exigir_vidas: bool | None = None,
) -> None:
    divs = divergencias_estruturais(matriz, vm, exigir_vidas=exigir_vidas)
    assert not divs, "paridade estrutural falhou:\n- " + "\n- ".join(divs)
