"""Frente 2.2 — identidade Newport no HTML exportado."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from newport_app.models.draft import EmpresaCliente
from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.branding import fonts_bytes_total, logo_bytes_len
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html,
    render_html_completo,
)
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.comparativo import ler_comparativo_congelado
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_apresentacao_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_tmp
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_fase2_tarefa2 import _aprovar, _stack
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito

_SCRIPT_TAG = re.compile(r"<script\b", re.IGNORECASE)


def test_data_usa_aprovado_em_estavel(tmp_path: Path):
    repo, _, snap_svc, apres = _stack(tmp_path, "data-aprov")
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(repo, snap_svc, rascunho)
    req = GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"])
    res1 = apres.gerar_html(rascunho.id, snap.id, req)
    html1 = (apres._entregaveis_dir / res1.caminho_relativo).read_text(encoding="utf-8")
    res2 = apres.gerar_html(rascunho.id, snap.id, req)
    html2 = (apres._entregaveis_dir / res2.caminho_relativo).read_text(encoding="utf-8")
    d1 = re.search(r"Revisado em (\d{2}/\d{2}/\d{4})", html1)
    d2 = re.search(r"Revisado em (\d{2}/\d{2}/\d{4})", html2)
    assert d1 and d2
    assert d1.group(1) == d2.group(1)
    # Conteúdo idêntico em gerações sucessivas do mesmo snapshot aprovado.
    assert html1 == html2


def test_builder_aprovado_em_fixo(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar_tmp(tmp_path, rascunho)
    fixo = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-1"], aprovado_em=fixo
    )
    assert vm.data_apresentacao == "15/03/2026"
    html = render_html(vm)
    assert "Revisado em 15/03/2026" in html


def test_sem_hash_nem_referencia_interna(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = [p.opcao_id for p in ler_comparativo_congelado(snap.payload).propostas]
    html = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids[:3])
    )
    assert "Referência interna" not in html
    assert snap.hash_sha256[:8] not in html
    assert snap.id not in html


def test_cliente_omitido_quando_ausente(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    rascunho.empresa_cliente = None
    rascunho.id = "sem-empresa"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=["op-1"])
    assert vm.subtitulo is None
    html = render_html(vm)
    assert ">Empresa<" not in html
    assert "Empresa Demonstração" not in html


def test_cliente_usa_empresa_cliente_nome(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    rascunho.empresa_cliente = EmpresaCliente(nome="Cliente ACME Ltda")
    rascunho.id = "com-empresa"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=["op-1"])
    assert vm.subtitulo == "Cliente ACME Ltda"
    assert "Cliente ACME Ltda" in render_html(vm)


def test_ivtec_capa_sem_base_nem_planos_atuais(tmp_path: Path):
    snap = _aprovar_tmp(tmp_path, _rascunho_ivtec_novo())
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-bronze", "op-prata"]
    )
    html = render_html(vm)
    assert "BASE MENSAL" not in html
    assert "PLANOS ATUAIS" not in html
    assert "Contrato atual" not in html
    assert "R$ —" not in html
    # Ausência de acomodação/validade usa «—» (como a matriz), não «R$ —».
    assert "Acomodação" in html
    assert "—" in html


def test_um_plano_exibe_consolidado_como_matriz(tmp_path: Path):
    """Matriz sempre mostra Consolidado quando há plano vigente — documento também."""
    rascunho = rascunho_demo_12_vidas()
    rascunho.id = "um-plano-consol"
    snap = _aprovar_tmp(tmp_path, rascunho)
    html = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=["op-1"])
    )
    assert "Consolidado" in html


def test_dois_planos_exibe_consolidado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = [p.opcao_id for p in ler_comparativo_congelado(snap.payload).propostas]
    assert "Consolidado" in render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )


def test_sem_script_e_poppins_embutida(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = [p.opcao_id for p in ler_comparativo_congelado(snap.payload).propostas]
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_b = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=ids, beneficiarios_agregados=True
    )
    html = render_html_completo(vm_r, vm_f, vm_b)
    assert _SCRIPT_TAG.search(html) is None
    assert "@font-face" in html
    assert "Poppins" in html
    assert "fonts.googleapis.com" not in html
    assert "data:image/png;base64," in html
    assert RENDERER_VERSAO.startswith("html@2.13")
    assert logo_bytes_len() > 10_000
    assert fonts_bytes_total() > 10_000


def test_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-id")
    snap = _aprovar(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=["op-1", "op-2"]),
    )
    assert snap_svc.obter_snapshot(snap.id).hash_sha256 == h_antes
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_antes}")
