"""Harness versionado de mutações — fecha cegueira do caminho compartilhado.

Cada mutação DEVE ser detectada por pelo menos uma asserção de origem ou de
paridade entre camadas. Mutação que passa = cegueira = falha do harness.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from newport_app.adapters import motor_out
from newport_app.presentation import html_renderer
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.paridade_estrutural import divergencias_estruturais
from newport_app.presentation.paridade_html import divergencias_html_vm
from newport_app.presentation.paridade_origem import divergencias_origem_completas
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_motor.result import ResultadoSubgrupo
from tests.gerador_celulas_estruturais import CelulaEstrutural, gerar_rascunho
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz

# Células representantes: cobrem renovação multi, regimes, várias propostas.
_CELULAS_HARNESS: tuple[CelulaEstrutural, ...] = (
    CelulaEstrutural("renovacao", 2, 1, 2),
    CelulaEstrutural("renovacao", 2, 2, 3),
    CelulaEstrutural("renovacao", 3, 2, 3),
)


@dataclass(frozen=True)
class ResultadoMutacao:
    id: int
    nome: str
    celulas_acusadas: int
    assercoes: tuple[str, ...]


@dataclass
class _EstadoPrep:
    rascunho: Any
    matriz: Any
    motor: Any
    estudo: Any
    policy: Any
    snap: Any
    ids: list[str]


def _preparar(tmp: Path, celula: CelulaEstrutural) -> _EstadoPrep:
    rascunho = gerar_rascunho(celula)
    sincronizar_cenarios(rascunho)
    matriz, motor = _calcular_matriz(rascunho)
    from newport_app.draft_compiler import compile
    from newport_app.policy.registry import default_registry

    rc = compile(rascunho, policy_registry=default_registry)
    assert rc.compilavel and rc.compilado is not None
    snap = _aprovar(tmp, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    return _EstadoPrep(
        rascunho=rascunho,
        matriz=matriz,
        motor=motor,
        estudo=rc.compilado.estudo_input,
        policy=rc.compilado.effective_policy,
        snap=snap,
        ids=ids,
    )


def _detectar(prep: _EstadoPrep) -> list[str]:
    """Roda asserções de origem + paridade matriz↔VM↔HTML (resumo e faixas)."""
    divs = divergencias_origem_completas(
        matriz=prep.matriz,
        motor=prep.motor,
        rascunho=prep.rascunho,
        estudo=prep.estudo,
        policy=prep.policy,
    )
    for modo in ("faixas", "resumo"):
        vm = construir_view_model(
            prep.snap, modo=modo, propostas_selecionadas=prep.ids
        )
        # Via módulo — patches em html_renderer.render_html / _render_* valem.
        html = html_renderer.render_html(vm)
        divs.extend(
            divergencias_origem_completas(
                matriz=prep.matriz,
                motor=prep.motor,
                rascunho=prep.rascunho,
                vm=vm,
                html=html,
                opcao_ids=prep.ids,
            )
        )
        divs.extend(
            divergencias_estruturais(prep.matriz, vm, rascunho=prep.rascunho)
        )
        divs.extend(divergencias_html_vm(vm, html))
    return divs


def _avaliar_mutacao(
    tmp: Path,
    mut_id: int,
    nome: str,
    aplicar: Callable[[], Iterator[None]],
) -> ResultadoMutacao:
    acusadas = 0
    tags: set[str] = set()
    for celula in _CELULAS_HARNESS:
        with aplicar():
            try:
                prep = _preparar(tmp / f"m{mut_id}-{celula.nome}", celula)
                divs = _detectar(prep)
            except Exception as exc:  # mutação que quebra o fluxo ainda conta
                acusadas += 1
                tags.add(f"excecao:{type(exc).__name__}")
                continue
            if divs:
                acusadas += 1
                for d in divs:
                    if "coluna_vs_grade" in d or "consolidado" in d:
                        tags.add("origem_coluna")
                    elif "acomodacao" in d or "operadora" in d or "nome " in d:
                        tags.add("origem_metadado")
                    elif "grade_vs_recalculo" in d:
                        tags.add("origem_grade")
                    elif "conjunto_colunas" in d:
                        tags.add("origem_conjunto")
                    elif "vm_vs_grade" in d or "vm_consolidado" in d:
                        tags.add("origem_vm")
                    elif "html_vs_grade" in d:
                        tags.add("origem_html")
                    elif "propostas:" in d or "planos:" in d:
                        tags.add("paridade_estrutural")
                    elif "camada" in d or "rotulo" in d.lower():
                        tags.add("paridade_html")
                    else:
                        tags.add("outra")
    return ResultadoMutacao(mut_id, nome, acusadas, tuple(sorted(tags)))


# --- Mutações ---------------------------------------------------------------

_orig_montar = motor_out._montar_propostas
_orig_planos = motor_out._montar_planos_atuais
_orig_render_resumo = html_renderer._render_resumo
_orig_th = html_renderer._th_proposta
_orig_rotulo = html_renderer._rotulo_proposta
_orig_tabela_faixas = html_renderer._render_tabela_faixas


@contextmanager
def mut_01_resumo_omite_plano() -> Iterator[None]:
    def wrapped(model, secao, rotulos, op_ids, *, seguro_novo):
        if not seguro_novo and secao.planos_atuais:
            secao = secao.model_copy(
                update={"planos_atuais": list(secao.planos_atuais)[1:]}
            )
        return _orig_render_resumo(
            model, secao, rotulos, op_ids, seguro_novo=seguro_novo
        )

    html_renderer._render_resumo = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        html_renderer._render_resumo = _orig_render_resumo


@contextmanager
def mut_02_adapter_plano_a_menos() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        planos, pend = _orig_planos(rascunho, resultado)
        if len(planos) >= 2:
            planos = planos[:-1]
        return planos, pend

    motor_out._montar_planos_atuais = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_planos_atuais = _orig_planos


@contextmanager
def mut_03_html_descarta_ultima_proposta() -> Iterator[None]:
    def wrapped(model, secao, rotulos, op_ids, *, seguro_novo):
        ids = list(op_ids[:-1]) if len(op_ids) >= 2 else list(op_ids)
        return _orig_render_resumo(
            model, secao, rotulos, ids, seguro_novo=seguro_novo
        )

    html_renderer._render_resumo = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        html_renderer._render_resumo = _orig_render_resumo


@contextmanager
def mut_04_rotulo_divergente_documento() -> Iterator[None]:
    # _rotulo_proposta prefere prop.plano_nome; mutar só o mapa rotulos é no-op
    # quando a lista de propostas não está vazia (resumo/faixas).
    def wrapped(op_id, propostas, rotulos):
        return f"ROTULO_ERRADO_{op_id}"

    html_renderer._rotulo_proposta = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        html_renderer._rotulo_proposta = _orig_rotulo


@contextmanager
def mut_05_ultima_faixa_some() -> Iterator[None]:
    def wrapped(plano, propostas, op_ids, rotulos, *, seguro_novo=False):
        if plano.faixas:
            plano = plano.model_copy(update={"faixas": list(plano.faixas)[:-1]})
        return _orig_tabela_faixas(
            plano, propostas, op_ids, rotulos, seguro_novo=seguro_novo
        )

    html_renderer._render_tabela_faixas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        html_renderer._render_tabela_faixas = _orig_tabela_faixas


@contextmanager
def mut_06_troca_valores_dois_planos() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        planos, pend = _orig_planos(rascunho, resultado)
        if len(planos) >= 2:
            a, b = planos[0], planos[1]
            planos[0] = a.model_copy(
                update={
                    "mensal_centavos": b.mensal_centavos,
                    "vigente_centavos": b.vigente_centavos,
                    "reajustado_centavos": b.reajustado_centavos,
                }
            )
            planos[1] = b.model_copy(
                update={
                    "mensal_centavos": a.mensal_centavos,
                    "vigente_centavos": a.vigente_centavos,
                    "reajustado_centavos": a.reajustado_centavos,
                }
            )
        return planos, pend

    motor_out._montar_planos_atuais = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_planos_atuais = _orig_planos


@contextmanager
def mut_07_perder_plano_em_tres() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        planos, pend = _orig_planos(rascunho, resultado)
        if len(planos) >= 3:
            planos = planos[:2]
        elif len(planos) >= 2:
            planos = planos[:-1]
        return planos, pend

    motor_out._montar_planos_atuais = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_planos_atuais = _orig_planos


@contextmanager
def mut_08_rotulo_so_matriz() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        props = _orig_montar(rascunho, resultado)
        if props:
            props[0] = props[0].model_copy(
                update={"plano_nome": f"ERRADO_{props[0].plano_nome}"}
            )
        return props

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


@contextmanager
def mut_09_coluna_sg_errado() -> Iterator[None]:
    """Troca valores entre subgrupos só na montagem da coluna (após grade)."""

    def wrapped(rascunho, resultado):
        props = _orig_montar(rascunho, resultado)
        for p in props:
            if len(p.subgrupos) >= 2:
                a, b = p.subgrupos[0], p.subgrupos[1]
                p.subgrupos[0] = a.model_copy(
                    update={
                        "proposta_centavos": b.proposta_centavos,
                        "proposta_reais": b.proposta_reais,
                        "diff_mes_centavos": b.diff_mes_centavos,
                        "diff_ano_centavos": b.diff_ano_centavos,
                    }
                )
                p.subgrupos[1] = b.model_copy(
                    update={
                        "proposta_centavos": a.proposta_centavos,
                        "proposta_reais": a.proposta_reais,
                        "diff_mes_centavos": a.diff_mes_centavos,
                        "diff_ano_centavos": a.diff_ano_centavos,
                    }
                )
        return props

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


@contextmanager
def mut_10_plano_usado_sumiu() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        props = _orig_montar(rascunho, resultado)
        return props[:-1] if len(props) >= 2 else props

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


@contextmanager
def mut_11_nao_usado_virou_coluna() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        props = _orig_montar(rascunho, resultado)
        usadas = {p.opcao_id for p in props}
        fora = [op for op in rascunho.opcoes_proposta if op.id not in usadas]
        if not props:
            return props
        if fora:
            fant = props[0].model_copy(
                update={
                    "opcao_id": fora[0].id,
                    "plano_nome": fora[0].plano_nome or "FANTASMA",
                    "cenario_id": f"col-{fora[0].id}",
                }
            )
        else:
            fant = props[0].model_copy(
                update={
                    "opcao_id": "op-fantasma-harness",
                    "plano_nome": "FANTASMA HARNESS",
                    "cenario_id": "col-fantasma",
                }
            )
        return props + [fant]

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


@contextmanager
def mut_12_acomodacao_outra_opcao() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        props = _orig_montar(rascunho, resultado)
        out = []
        for p in props:
            wrong = (
                "Enfermaria"
                if (p.acomodacao or "") != "Enfermaria"
                else "Apartamento"
            )
            out.append(p.model_copy(update={"acomodacao": wrong}))
        return out

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


@contextmanager
def mut_13_troca_sg_tres_camadas() -> Iterator[None]:
    """Mesmo que M9: simétrico nas três camadas (todas leem _montar_propostas)."""
    with mut_09_coluna_sg_errado():
        yield


@contextmanager
def mut_14_consolidado_soma_errado() -> Iterator[None]:
    def wrapped(rascunho, resultado):
        props = _orig_montar(rascunho, resultado)
        out = []
        for p in props:
            if p.numerico and p.numerico.proposta_mensal_centavos is not None:
                num = p.numerico.model_copy(
                    update={
                        "proposta_mensal_centavos": p.numerico.proposta_mensal_centavos
                        + 1
                    }
                )
                out.append(p.model_copy(update={"numerico": num}))
            else:
                out.append(p)
        return out

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


@contextmanager
def mut_15_grade_celula_outra_opcao() -> Iterator[None]:
    """Troca o conteúdo de duas células da grade (mesmos subgrupos, opções distintas)."""

    def wrapped(rascunho, resultado):
        grade = list(resultado.grade_opcao_subgrupo)
        # Emparelha por subgrupo e troca proposta entre duas opções
        por_sg: dict[str, list[ResultadoSubgrupo]] = {}
        for cel in grade:
            por_sg.setdefault(cel.subgrupo_id, []).append(cel)
        novos: list[ResultadoSubgrupo] = []
        vistos: set[int] = set()
        for cel in grade:
            if id(cel) in vistos:
                continue
            pares = por_sg.get(cel.subgrupo_id, [])
            if len(pares) >= 2:
                a, b = pares[0], pares[1]
                novos.append(
                    a.model_copy(
                        update={
                            "subtotal_proposta_centavos": b.subtotal_proposta_centavos,
                            "vidas": b.vidas,
                        }
                    )
                )
                novos.append(
                    b.model_copy(
                        update={
                            "subtotal_proposta_centavos": a.subtotal_proposta_centavos,
                            "vidas": a.vidas,
                        }
                    )
                )
                vistos.add(id(a))
                vistos.add(id(b))
            else:
                novos.append(cel)
                vistos.add(id(cel))
        resultado_mut = resultado.model_copy(update={"grade_opcao_subgrupo": novos})
        return _orig_montar(rascunho, resultado_mut)

    motor_out._montar_propostas = wrapped  # type: ignore[assignment]
    try:
        yield
    finally:
        motor_out._montar_propostas = _orig_montar


MUTACOES: list[tuple[int, str, Callable[[], Iterator[None]]]] = [
    (1, "resumo_omite_plano", mut_01_resumo_omite_plano),
    (2, "adapter_plano_a_menos", mut_02_adapter_plano_a_menos),
    (3, "html_descarta_ultima_proposta", mut_03_html_descarta_ultima_proposta),
    (4, "rotulo_divergente_documento", mut_04_rotulo_divergente_documento),
    (5, "ultima_faixa_some", mut_05_ultima_faixa_some),
    (6, "troca_valores_dois_planos", mut_06_troca_valores_dois_planos),
    (7, "perder_plano_em_tres", mut_07_perder_plano_em_tres),
    (8, "rotulo_so_matriz", mut_08_rotulo_so_matriz),
    (9, "coluna_sg_errado", mut_09_coluna_sg_errado),
    (10, "plano_usado_sumiu", mut_10_plano_usado_sumiu),
    (11, "nao_usado_virou_coluna", mut_11_nao_usado_virou_coluna),
    (12, "acomodacao_outra_opcao", mut_12_acomodacao_outra_opcao),
    (13, "troca_sg_tres_camadas", mut_13_troca_sg_tres_camadas),
    (14, "consolidado_soma_errado", mut_14_consolidado_soma_errado),
    (15, "grade_celula_outra_opcao", mut_15_grade_celula_outra_opcao),
]


def rodar_todas(tmp: Path) -> list[ResultadoMutacao]:
    return [
        _avaliar_mutacao(tmp, mid, nome, aplicar)
        for mid, nome, aplicar in MUTACOES
    ]
