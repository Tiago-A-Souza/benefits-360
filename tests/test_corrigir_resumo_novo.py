"""Correção — resumo executivo em seguro novo com uma linha por proposta."""

from __future__ import annotations

import re
from pathlib import Path

from newport_app.models.snapshot import AprovarSnapshotRequest, GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.paridade_html import divergencias_html_vm
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)


def _stack(tmp_path: Path, nome: str):
    from tests.test_fase2_tarefa2 import _stack as _stack_fase2

    return _stack_fase2(tmp_path, nome)


def _vm_html(tmp_path: Path, rascunho, *, modo: str, ids: list[str] | None = None):
    from datetime import datetime, timezone

    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    if ids is None:
        ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    aprov = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    vm = construir_view_model(
        snap,
        modo=modo,
        propostas_selecionadas=ids,
        beneficiarios_agregados=(modo != "beneficiario"),
        aprovado_em=aprov,
    )
    return vm, render_html(vm), matriz, snap, ids


def test_01_ivtec_resumo_lista_propostas_com_totais(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    vm, html, _, _, ids = _vm_html(tmp_path, rascunho, modo="resumo")
    assert set(ids) == {"op-bronze", "op-prata"}
    assert "3.741,89" in html
    assert "5.652,04" in html
    assert "BRONZE SP MAIS COPART TP" in html or "BRONZE" in html
    assert "PRATA QC COPART TP" in html or "PRATA" in html
    # Uma linha por proposta — não a única «Diferença vs menor».
    assert html.count("<tbody>") >= 1
    assert "Proposta</th>" in html
    assert "Total mensal" in html
    for op_id in ids:
        assert vm.totais_gerais.propostas[op_id] is not None
        assert formatar_reais(vm.totais_gerais.propostas[op_id]) in html


def test_02_totais_resumo_iguais_aos_de_faixas(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    vm_r, html_r, _, snap, ids = _vm_html(tmp_path / "r", rascunho, modo="resumo")
    vm_f = construir_view_model(
        snap,
        modo="faixas",
        propostas_selecionadas=ids,
        beneficiarios_agregados=True,
    )
    html_f = render_html(vm_f)
    for op_id in ids:
        total_r = vm_r.totais_gerais.propostas[op_id]
        total_f = vm_f.totais_gerais.propostas[op_id]
        assert total_r == total_f
        texto = formatar_reais(total_r)
        assert texto in html_r
        assert texto in html_f


def test_03_uma_proposta_exibe_referencia_nao_zero(tmp_path: Path):
    base = _rascunho_ivtec_novo()
    op = base.opcoes_proposta[0]
    rascunho = base.model_copy(
        update={"id": "ivtec-uma", "opcoes_proposta": [op], "cenarios": []}
    )
    sincronizar_cenarios(rascunho)
    vm, html, _, _, ids = _vm_html(tmp_path, rascunho, modo="resumo")
    assert len(ids) == 1
    assert "referência" in html
    assert "−R$ 0,00" not in html
    assert "-R$ 0,00" not in html
    # Total da única proposta aparece.
    total = vm.totais_gerais.propostas[ids[0]]
    assert total is not None
    assert formatar_reais(total) in html
    assert vm.totais_gerais.diff_mensal.get(ids[0]) == 0


def test_04_anistia_resumo_renovacao_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, html, _, _, _ = _vm_html(tmp_path, rascunho, modo="resumo")
    assert "Indicador</th>" in html
    assert "Consolidado" in html
    assert "Diferença mensal" in html
    assert "Diferença anual" in html
    assert "Proposta</th>" not in html
    # Estrutura de renovação + valores do gabarito Anistia (dois planos).
    for trecho in ("48.479,31", "29.386,76", "19.092,55", "23.607,17", "6.100,61"):
        assert trecho in html


def test_05_inventario_html_vm_sem_xfail(tmp_path: Path):
    for factory, rotulo in (
        (_rascunho_ivtec_novo, "novo_0_1_2"),
        (
            lambda: _rascunho_ivtec_novo().model_copy(
                update={
                    "id": "uma",
                    "opcoes_proposta": [_rascunho_ivtec_novo().opcoes_proposta[0]],
                    "cenarios": [],
                }
            ),
            "novo_0_1_1",
        ),
    ):
        rascunho = factory()
        sincronizar_cenarios(rascunho)
        for modo in ("resumo", "faixas", "beneficiario"):
            vm, html, _, _, _ = _vm_html(tmp_path / f"{rotulo}-{modo}", rascunho, modo=modo)
            divs = divergencias_html_vm(vm, html)
            assert not divs, f"{rotulo}/{modo}: {divs}"


def test_06_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    sincronizar_cenarios(rascunho)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-resumo-novo")
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(g.snapshot_id)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(
            modo="completo",
            propostas_selecionadas=["op-bronze", "op-prata"],
        ),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_07_diffs_vêm_do_vm_nao_do_renderer(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    vm, html, matriz, _, ids = _vm_html(tmp_path, rascunho, modo="resumo")
    for op_id in ids:
        n = next(p.numerico for p in matriz.propostas if p.opcao_id == op_id)
        assert vm.totais_gerais.diff_mensal[op_id] == n.diff_mes_centavos
        assert vm.totais_gerais.diff_anual[op_id] == n.diff_ano_centavos
        prop = next(p for s in vm.secoes_regime for p in s.propostas if p.opcao_id == op_id)
        assert prop.diff_mensal_centavos == n.diff_mes_centavos
    # Renderer não inventa: a maior proposta mostra o diff positivo do VM.
    prata = vm.totais_gerais.diff_mensal["op-prata"]
    assert prata and prata > 0
    assert formatar_reais(prata) in html
    bronze_diff = vm.totais_gerais.diff_mensal["op-bronze"]
    assert bronze_diff == 0
    assert "referência" in html
