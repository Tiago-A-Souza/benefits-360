"""Fase 1 — assert estrutural matriz ↔ VM + inventário HTML ↔ VM (11 casos)."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_estrutural import (
    assert_paridade_estrutural,
    divergencias_estruturais,
)
from newport_app.presentation.paridade_html import (
    assert_paridade_html_vm,
    divergencias_html_vm,
    inventariar_html,
    inventariar_vm,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from tests.test_comparativo_multiplas_propostas import _rascunho_quatro_propostas
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_etapa_281 import _rascunho_duas_propostas
from tests.test_etapa_282 import _rascunho_regimes_diferentes
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    _rascunho_n_subgrupos,
)


def _rascunho_novo_uma_proposta():
    """novo × 0 planos × 1 regime × 1 proposta."""
    base = _rascunho_ivtec_novo()
    op = base.opcoes_proposta[0]
    rascunho = base.model_copy(
        update={
            "id": "ivtec-uma-prop",
            "opcoes_proposta": [op],
            "cenarios": [],
        }
    )
    sincronizar_cenarios(rascunho)
    return rascunho


_CASOS = [
    ("renovacao_1_1_1", lambda: _rascunho_n_subgrupos(1)),
    ("renovacao_1_1_2", _rascunho_duas_propostas),
    ("renovacao_1_2_2", _rascunho_regimes_diferentes),
    ("renovacao_1_2_4", _rascunho_quatro_propostas),
    ("renovacao_2_1_1", lambda: _rascunho_n_subgrupos(2)),
    ("renovacao_2_1_2", lambda: _rascunho_n_subgrupos(2, extra_opcoes=1)),
    ("renovacao_2_2_2", lambda: _rascunho_dois_planos_gabarito(reajuste_bps=1200)),
    ("renovacao_2_2_6", _rascunho_anistia_seis),
    ("renovacao_3_1_1", lambda: _rascunho_n_subgrupos(3)),
    ("novo_0_1_1", _rascunho_novo_uma_proposta),
    ("novo_0_1_2", _rascunho_ivtec_novo),
]

# Defeitos do resumo seguro novo corrigidos — xfail removido.
def _params_html_vm():
    for rotulo, factory in _CASOS:
        for modo in ("resumo", "faixas", "beneficiario"):
            yield pytest.param(
                rotulo,
                factory,
                modo,
                id=f"{modo}-{rotulo}",
            )


@pytest.mark.parametrize("rotulo,factory", _CASOS)
@pytest.mark.parametrize("modo", ["resumo", "faixas", "beneficiario"])
def test_paridade_estrutural_11_casos(tmp_path: Path, rotulo: str, factory, modo: str):
    rascunho = factory()
    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    assert ids, f"{rotulo}: nenhuma proposta calculada"
    vm = construir_view_model(
        snap,
        modo=modo,
        propostas_selecionadas=ids,
        beneficiarios_agregados=(modo != "beneficiario"),
    )
    assert_paridade_estrutural(matriz, vm, rascunho=rascunho)


@pytest.mark.parametrize("rotulo,factory,modo", list(_params_html_vm()))
def test_paridade_html_vm_11_casos(tmp_path: Path, rotulo: str, factory, modo: str):
    rascunho = factory()
    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    assert ids, f"{rotulo}: nenhuma proposta calculada"
    vm = construir_view_model(
        snap,
        modo=modo,
        propostas_selecionadas=ids,
        beneficiarios_agregados=(modo != "beneficiario"),
    )
    html_doc = render_html(vm)
    assert_paridade_html_vm(vm, html_doc)


def test_coleta_divergencias_fase1(tmp_path: Path):
    """Imprime inventário camada 1 (matriz↔VM) e camada 2 (HTML↔VM). Sempre passa."""
    relatorio1: list[str] = []
    relatorio2: list[str] = []
    n1 = n2 = 0
    for rotulo, factory in _CASOS:
        rascunho = factory()
        sincronizar_cenarios(rascunho)
        matriz, _ = _calcular_matriz(rascunho)
        snap = _aprovar(tmp_path / rotulo, rascunho)
        ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
        for modo in ("resumo", "faixas", "beneficiario"):
            vm = construir_view_model(
                snap,
                modo=modo,
                propostas_selecionadas=ids,
                beneficiarios_agregados=(modo != "beneficiario"),
            )
            divs1 = divergencias_estruturais(matriz, vm, rascunho=rascunho)
            if divs1:
                n1 += 1
                relatorio1.append(f"### {rotulo} / modo={modo}")
                relatorio1.extend(f"  - {d}" for d in divs1)
            html_doc = render_html(vm)
            divs2 = divergencias_html_vm(vm, html_doc)
            if divs2:
                n2 += 1
                iv, ih = inventariar_vm(vm), inventariar_html(html_doc)
                relatorio2.append(
                    f"### {rotulo} / modo={modo} "
                    f"(vm_faixas={len(iv.faixas)} html_faixas={len(ih.faixas)} "
                    f"html_linhas={len(ih.linhas)})"
                )
                relatorio2.extend(f"  - {d}" for d in divs2)
    print(f"CAMADA1_CASOS_COM_DIVERGENCIA={n1}")
    print("\n".join(relatorio1) if relatorio1 else "CAMADA1_NENHUMA_DIVERGENCIA")
    print(f"CAMADA2_CASOS_COM_DIVERGENCIA={n2}")
    print("\n".join(relatorio2) if relatorio2 else "CAMADA2_NENHUMA_DIVERGENCIA")
    assert True
