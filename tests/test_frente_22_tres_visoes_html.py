"""Frente 2.2 — três visões no HTML exportado (CSS puro, sem nomes no cliente)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html,
    render_html_completo,
)
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_tmp
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_fase2_tarefa2 import _aprovar, _stack
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito

_FIXTURE_SEIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "anistia_seis_propostas.json"
)

_SCRIPT_TAG = re.compile(r"<script\b", re.IGNORECASE)


def _html_completo_anistia(tmp_path: Path) -> tuple[str, object]:
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_tmp(tmp_path, rascunho)
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    ids = [p["id"] for p in spec["propostas"]]
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_g = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=ids,
        beneficiarios_agregados=False,
    )
    return render_html_completo(vm_r, vm_f, vm_g), snap


def test_01_arquivo_contem_tres_visoes(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert 'id="visao-resumo"' in html
    assert 'id="visao-faixas"' in html
    assert 'id="visao-benef"' in html
    assert "Resumo executivo" in html
    assert "Faixas etárias" in html
    assert "Por grupo familiar" in html
    assert "Por beneficiário" not in html
    assert RENDERER_VERSAO.startswith("html@")


def test_02_sem_javascript_e_radios_css(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert _SCRIPT_TAG.search(html) is None
    assert 'name="doc-visao"' in html
    assert 'id="tab-resumo"' in html
    assert 'id="tab-faixas"' in html
    assert 'id="tab-benef"' in html
    assert 'id="tab-todas"' in html
    assert "#tab-resumo:checked ~ .doc-corpo .visao-resumo" in html
    assert "#tab-todas:checked ~ .doc-corpo .visao" in html


def test_03_botao_ver_tres_e_voltar_ao_resumo(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "Ver todas as visões" in html
    assert "Voltar às abas" in html
    assert 'for="tab-todas"' in html
    # Voltar seleciona tab-resumo (mesmo name → sai de «todas»).
    assert 'class="doc-btn-voltar" for="tab-resumo"' in html
    assert 'id="tab-resumo"' in html and "checked" in html.split('id="tab-resumo"')[1][:80]


def test_04_completo_com_nomes_isolado_grupo_sem_nomes(tmp_path: Path):
    repo, _, snap_svc, apres = _stack(tmp_path, "pii-completo")
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(repo, snap_svc, rascunho)
    nomes = sorted({v.nome for v in rascunho.vidas if (v.nome or "").strip()})
    assert nomes, "fixture deve ter nomes para o teste de LGPD"
    res = apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=["op-1"]),
    )
    assert res.aviso_dados_pessoais
    assert res.modo == "completo"
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    assert "<div class='aviso-pii'>" not in html
    assert "Este material contém nomes de beneficiários" not in html
    assert any(n in html for n in nomes)
    res_iso = apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="grupo_familiar", propostas_selecionadas=["op-1"]),
    )
    assert res_iso.aviso_dados_pessoais is None
    html_iso = (apres._entregaveis_dir / res_iso.caminho_relativo).read_text(encoding="utf-8")
    for nome in nomes:
        assert nome not in html_iso, f"nome vazou no isolado agregado: {nome}"
    assert "Grupo 1" in html_iso or "Membro" in html_iso


def test_05_css_impressao_respeita_visibilidade(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert ".visao { display: none; }" in html
    assert "@media print" in html
    assert ".doc-controles" in html and "no-print" in html
    # Uma aba: só a visão checked fica display:block; «todas» força as três.
    assert "#tab-faixas:checked ~ .doc-corpo .visao-faixas" in html
    assert "#tab-todas:checked ~ .doc-corpo .visao { display: block !important; }" in html


def test_06_gabarito_executivo_r1_copart_30(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "Executivo R1" in html
    assert "44.819,89" in html
    assert "13.041,45" in html
    assert "Coparticipação" in html or "copart" in html.lower()


def test_07_vigente_ausente_nas_tres_visoes(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "Atual vigente" not in html
    assert not any(
        "vigente" in trecho.lower() and "reajust" not in trecho.lower()
        for trecho in re.findall(r">[^<]{0,80}<", html)
        if "vigente" in trecho.lower()
    )
    # Cabeçalhos/células não usam o rótulo vigente (2.1).
    assert "Vigente" not in html


def test_08_gabarito_anistia_consolidados(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "48.479,31" in html
    assert "29.386,76" in html
    assert "19.092,55" in html
    assert "21.354,64" in html
    assert "5.518,50" in html
    assert "23.607,17" in html
    assert "6.100,61" in html
    # Centavos canônicos do fixture seis propostas (bronze/prata no consolidado).
    assert formatar_reais(4_847_931) == "R$ 48.479,31"


def test_09_hash_snapshot_inalterado_pela_apresentacao(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-22")
    snap = _aprovar(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=["op-1", "op-2"]),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    # Digests explícitos para o relatório da frente.
    assert len(h_antes) == 64
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_11_acessibilidade_abas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert 'role="tabpanel"' in html
    assert "focus-visible" in html
    assert 'aria-label="Resumo executivo"' in html
    assert 'aria-controls="visao-resumo"' in html


def test_tamanho_completo_maior_que_resumo(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_tmp(tmp_path, rascunho)
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    ids = [p["id"] for p in spec["propostas"]]
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_g = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=ids,
        beneficiarios_agregados=False,
    )
    html_resumo = render_html(vm_r)
    html_completo = render_html_completo(vm_r, vm_f, vm_g)
    assert len(html_completo) > len(html_resumo)
    print(f"TAMANHO_RESUMO={len(html_resumo)}")
    print(f"TAMANHO_COMPLETO={len(html_completo)}")
