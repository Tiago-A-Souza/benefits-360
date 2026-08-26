"""Fase 2 — paridade estrutural nas células geradas (48 − inválidas).

Duas camadas × quatro modos. Defeitos de produto: xfail(strict), sem correção.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html, render_html_completo
from newport_app.presentation.paridade_estrutural import (
    assert_paridade_estrutural,
    divergencias_estruturais,
)
from newport_app.presentation.paridade_html import (
    assert_paridade_html_vm,
    divergencias_html_vm,
    inventariar_html,
    inventariar_vm,
    valores_principais_vm,
)
from newport_app.presentation.formatacao import formatar_reais
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from tests.gerador_celulas_estruturais import (
    CelulaEstrutural,
    enumerar_celulas_invalidas,
    enumerar_celulas_totais,
    enumerar_celulas_validas,
    gerar_rascunho,
)
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz

_APROV = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
_MODOS = ("resumo", "faixas", "beneficiario", "completo")

# Defeitos de produto conhecidos nesta grade: nenhum até agora.
# Quando a coleta achar falha, registre aqui:
#   "modo-formato_P_R_N": "motivo curto (camada/modo)"
_XFAIL_POR_ID: dict[str, str] = {}


def _xfail_mark(test_id: str):
    motivo = _XFAIL_POR_ID.get(test_id)
    if not motivo:
        return ()
    return (pytest.mark.xfail(reason=motivo, strict=True),)


def test_contagem_celulas_gerador():
    totais = enumerar_celulas_totais()
    validas = enumerar_celulas_validas()
    invalidas = enumerar_celulas_invalidas()
    assert len(totais) == 48
    assert len(validas) + len(invalidas) == 48
    assert len(validas) == 36
    assert len(invalidas) == 12
    # Ênfases do diagnóstico presentes nas válidas.
    nomes = {c.nome for c in validas}
    assert "renovacao_3_3_3" in nomes or "renovacao_3_3_6" in nomes
    assert "novo_0_2_3" in nomes  # multi-regime + 3 propostas
    assert "novo_0_1_6" in nomes  # 6+ propostas
    assert "renovacao_3_2_3" in nomes  # 3 planos × 2+ regimes
    assert "novo_0_1_3" in nomes  # IVTEC real (3 propostas)


def _preparar(tmp_path: Path, celula: CelulaEstrutural):
    rascunho = gerar_rascunho(celula)
    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    assert ids, f"{celula.nome}: nenhuma proposta calculada"
    assert len(ids) == celula.n_propostas
    return rascunho, matriz, snap, ids


def _vm(snap, modo: str, ids: list[str]):
    return construir_view_model(
        snap,
        modo=modo,
        propostas_selecionadas=ids,
        beneficiarios_agregados=(modo != "beneficiario"),
        aprovado_em=_APROV,
    )


def divergencias_html_completo(vm_r, vm_f, vm_b, html: str) -> list[str]:
    """Inventário do documento completo contra os três VMs (sem lista à mão)."""
    ih = inventariar_html(html)
    divs: list[str] = []
    iv_r, iv_f, iv_b = inventariar_vm(vm_r), inventariar_vm(vm_f), inventariar_vm(vm_b)

    falta_prop = sorted(iv_r.propostas - ih.propostas)
    if falta_prop:
        divs.append(f"completo: propostas ausentes no HTML: {falta_prop}")

    falta_fx = sorted(iv_f.faixas - ih.faixas)
    if falta_fx:
        divs.append(f"completo: faixas ausentes no HTML: {falta_fx}")

    if iv_f.planos:
        falta_pl = sorted(iv_f.planos - ih.planos)
        if falta_pl:
            divs.append(f"completo: planos ausentes no HTML: {falta_pl}")

    if iv_b.vidas:
        falta_v = sorted(iv_b.vidas - ih.vidas)
        if falta_v:
            divs.append(
                f"completo: vidas ausentes no HTML ({len(falta_v)}): {falta_v[:8]}"
                + ("…" if len(falta_v) > 8 else "")
            )

    principais = valores_principais_vm(vm_r) | valores_principais_vm(vm_f)
    ausentes = sorted(principais - ih.valores_centavos)
    if ausentes:
        divs.append(
            "completo: valores principais ausentes: "
            + ", ".join(formatar_reais(c) for c in ausentes[:8])
            + ("…" if len(ausentes) > 8 else "")
        )

    modelo_vals = (
        set(iv_r.valores_centavos)
        | set(iv_f.valores_centavos)
        | set(iv_b.valores_centavos)
        | {0}
    )
    inventados = sorted(ih.valores_centavos - modelo_vals)
    if inventados:
        divs.append(
            "completo: valores no HTML ausentes do modelo: "
            + ", ".join(formatar_reais(c) for c in inventados[:8])
            + ("…" if len(inventados) > 8 else "")
        )
    return divs


def _rodar_celula_modo(
    tmp_path: Path, celula: CelulaEstrutural, modo: str
) -> list[str]:
    _, matriz, snap, ids = _preparar(tmp_path, celula)
    divs: list[str] = []
    if modo == "completo":
        vm_r = _vm(snap, "resumo", ids)
        vm_f = _vm(snap, "faixas", ids)
        vm_b = _vm(snap, "beneficiario", ids)
        for rotulo, vm in (("resumo", vm_r), ("faixas", vm_f), ("beneficiario", vm_b)):
            d = divergencias_estruturais(matriz, vm)
            divs.extend(f"camada1/{rotulo}: {x}" for x in d)
        html = render_html_completo(vm_r, vm_f, vm_b)
        divs.extend(f"camada2/completo: {x}" for x in divergencias_html_completo(vm_r, vm_f, vm_b, html))
        return divs

    vm = _vm(snap, modo, ids)
    d1 = divergencias_estruturais(matriz, vm)
    divs.extend(f"camada1: {x}" for x in d1)
    html = render_html(vm)
    d2 = divergencias_html_vm(vm, html)
    divs.extend(f"camada2: {x}" for x in d2)
    return divs


def _params_celula_modo():
    for celula in enumerar_celulas_validas():
        for modo in _MODOS:
            tid = f"{modo}-{celula.nome}"
            yield pytest.param(
                celula,
                modo,
                id=tid,
                marks=_xfail_mark(tid),
            )


@pytest.mark.parametrize("celula,modo", list(_params_celula_modo()))
def test_paridade_celula_estrutural(
    tmp_path: Path, celula: CelulaEstrutural, modo: str
):
    divs = _rodar_celula_modo(tmp_path / celula.nome / modo, celula, modo)
    assert not divs, f"{celula.nome}/{modo} falhou:\n- " + "\n- ".join(divs)


def test_coleta_divergencias_fase2(tmp_path: Path):
    """Inventário de falhas (sempre passa). Imprime combinação × camada × modo."""
    relatorio: list[str] = []
    n_falha = 0
    for celula in enumerar_celulas_validas():
        for modo in _MODOS:
            divs = _rodar_celula_modo(tmp_path / celula.nome / modo, celula, modo)
            if divs:
                n_falha += 1
                relatorio.append(f"### {celula.nome} / modo={modo}")
                relatorio.extend(f"  - {d}" for d in divs)
    print(f"CELULAS_VALIDAS={len(enumerar_celulas_validas())}")
    print(f"CELULAS_INVALIDAS={len(enumerar_celulas_invalidas())}")
    print(f"CASOS_MODO_COM_FALHA={n_falha}")
    print("\n".join(relatorio) if relatorio else "NENHUMA_FALHA")
    assert True
