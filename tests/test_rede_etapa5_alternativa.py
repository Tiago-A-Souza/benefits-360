"""Rede na etapa 5 — alternativa ao sandbox HTML (branch rede-etapa5-alternativa)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newport_app.models.draft import RascunhoEstudo, SelecaoRedeRascunho
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.services.rede_selecao import excluidos_rede, salvar_selecao_rede
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


def _html_completo_etapa5(tmp_path: Path, rascunho: RascunhoEstudo, cen_id: str):
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    excl = excluidos_rede(rascunho)
    rede = montar_rede_apresentacao(
        rascunho, [cen_id], excluidos=excl
    )
    html = render_html_completo(
        vm, vm, vm, rede=rede, rede_entrega_cliente=True
    )
    return html, rede


def test_01_passos_incluem_rede_antes_do_comparativo():
    src = (ROOT / "web" / "src" / "fluxo" / "passos.js").read_text(encoding="utf-8")
    assert '{ chave: "rede"' in src
    idx_rede = src.index('"rede"')
    idx_cmp = src.index('"comparativo"')
    assert idx_rede < idx_cmp


def test_02_documento_gerado_sem_sandbox_na_rede(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    html, _ = _html_completo_etapa5(tmp_path, rascunho, cen_id)
    rede = html.split('id="visao-rede"', 1)[-1]
    assert "rede-btn-confirmar" not in rede
    assert "rede-sandbox-bar" not in rede.split("</style>", 1)[-1]
    assert not re.search(r"<script(?![^>]*application/json)", rede, re.I)


def test_03_exclusao_remove_prestador_do_documento(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc and doc.secoes[0].blocos
    lid = doc.secoes[0].blocos[0].linhas[0].linha_id
    salvar_selecao_rede(rascunho, [lid], revisada=True)
    html, _ = _html_completo_etapa5(tmp_path, rascunho, cen_id)
    assert lid not in html or html.count(lid) == 0


def test_04_selecao_rede_persiste_no_rascunho():
    r = RascunhoEstudo.model_validate(
        {
            "rascunho_versao": "1.0",
            "policy_set_versao": "1",
            "id": "x",
            "titulo": "t",
            "vidas": [],
        }
    )
    salvar_selecao_rede(r, ["id-a", "id-b"], revisada=True, ids_validos={"id-a", "id-b", "id-c"})
    assert r.selecao_rede
    assert r.selecao_rede.excluidos == ["id-a", "id-b"]
    assert r.selecao_rede.revisada is True


def test_05_novo_prestador_nao_esta_na_lista_de_exclusao():
    """Exclusão gravada — id novo não é excluído por omissão."""
    r = RascunhoEstudo.model_validate(
        {
            "rascunho_versao": "1.0",
            "policy_set_versao": "1",
            "id": "x",
            "titulo": "t",
            "vidas": [],
            "selecao_rede": {"excluidos": ["velho"], "revisada": True},
        }
    )
    assert "novo" not in excluidos_rede(r)
