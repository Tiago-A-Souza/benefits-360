"""REDE fase D2 — sandbox do corretor na aba Rede."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.presentation.rede_sandbox import (
    hash_desbloqueio_estudo,
    nome_arquivo_para_cliente,
)
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario
from tests.test_regras_comerciais import _html_de

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


def _html_completo_rede(tmp_path: Path, estudo_id: str | None = "anistia-d2"):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    if estudo_id:
        rascunho = rascunho.model_copy(update={"id": estudo_id})
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc is not None
    html = render_html_completo(
        vm, vm, vm, rede=doc, estudo_id=estudo_id if estudo_id else None
    )
    return html, rascunho, cen_id


def _estado(html: str) -> dict:
    m = re.search(
        r"<script type=['\"]application/json['\"] id=['\"]newport-rede-state['\"]>(.*?)</script>",
        html,
        re.S,
    )
    assert m, "estado embutido ausente"
    return json.loads(m.group(1))


def test_01_documento_novo_modo_edicao(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    st = _estado(html)
    assert st["mode"] == "edit"
    assert st["excluded"] == []
    assert "rede-sandbox-bar" in html
    assert "rede-btn-confirmar" in html


def test_02_confirmar_esconde_controles_no_estado_final(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    st = _estado(html)
    st["mode"] = "final"
    st["excluded"] = ["abc"]
    # Simula arquivo salvo após confirmar
    html2 = re.sub(
        r"(<script type=['\"]application/json['\"] id=['\"]newport-rede-state['\"]>).*?(</script>)",
        lambda m: m.group(1) + json.dumps(st, separators=(",", ":")) + m.group(2),
        html,
        count=1,
    )
    st2 = _estado(html2)
    assert st2["mode"] == "final"


def test_03_reabrir_mantem_modo_final(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    html3 = html.replace('"mode":"edit"', '"mode":"final"')
    assert _estado(html3)["mode"] == "final"


def test_04_botao_editar_no_rodape(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert "rede-btn-editar" in html


def test_05_hash_desbloqueio_coerente(tmp_path: Path):
    eid = "estudo-secreto-xyz"
    html, rasc, _ = _html_completo_rede(tmp_path, estudo_id=eid)
    expect = hash_desbloqueio_estudo(eid)
    assert f"data-unlock='{expect}'" in html or f'data-unlock="{expect}"' in html


def test_06_id_estudo_nao_aparece_no_html(tmp_path: Path):
    eid = "estudo-secreto-xyz-unico"
    html, _, _ = _html_completo_rede(tmp_path, estudo_id=eid)
    assert eid not in html


def test_07_filtros_zona_municipio_busca_presentes(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert "rede-filtro-zona" in html
    assert "rede-filtro-mun" in html
    assert "rede-filtro-nome" in html


def test_08_linhas_tem_checkbox_e_data_rede_id(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert html.count("data-rede-id=") >= 5
    assert "rede-sandbox-check" in html


def test_09_marcar_bloco_botao(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert "rede-marcar-bloco" in html


def test_10_contagem_por_bloco_mantida(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert "Prestadores cobertos" in html
    assert "cont-rede" in html


def test_11_quatro_abas_sem_script(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    antes = html.split('id="visao-rede"', 1)[0]
    assert "<script" not in antes.lower()


def test_12_degradacao_sem_js_classe_no_js(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert "rede-sandbox-no-js" in html
    assert "rede-sandbox-js-only" in html


def test_13_impressao_esconde_controles_css(tmp_path: Path):
    from newport_app.presentation import html_renderer as hr

    assert "@media print" in hr._CSS
    assert ".rede-sandbox-js-only" in hr._CSS


def test_14_sem_local_storage_no_script():
    js = (ROOT / "src/newport_app/presentation/rede_sandbox.js").read_text(
        encoding="utf-8"
    )
    assert "localStorage" not in js
    assert "sessionStorage" not in js


def test_15_script_usa_subtle_digest():
    js = (ROOT / "src/newport_app/presentation/rede_sandbox.js").read_text(
        encoding="utf-8"
    )
    assert "crypto.subtle.digest" in js
    assert "SHA-256" in js


def test_16_gabarito_anistia_html_intacto(tmp_path: Path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "48.479,31" in html


def test_17_quatro_abas_inalteradas(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    sem = render_html_completo(vm, vm, vm, rede=None)
    com = render_html_completo(
        vm,
        vm,
        vm,
        rede=montar_rede_apresentacao(rascunho, [cen_id]),
        estudo_id=rascunho.id,
    )
    extrair = lambda h: re.search(r'id="visao-resumo"[^>]*>(.*?)</section>', h, re.S).group(1)
    assert extrair(sem) == extrair(com)


def test_18_estrutura_d1_secoes_colunas(tmp_path: Path):
    html, _, _ = _html_completo_rede(tmp_path)
    assert "secao-rede" in html
    assert "bairro-rede" in html or "Contrato atual" in html
    assert "tabela-rede" in html


def test_19_hash_python_igual_embed(tmp_path: Path):
    eid = "demo-12"
    h = hash_desbloqueio_estudo(eid)
    assert len(h) == 64
    html, _, _ = _html_completo_rede(tmp_path, estudo_id=eid)
    assert h in html


def test_20_nome_download_para_cliente(tmp_path: Path):
    origem = "apresentacao_completo_71e431d7.html"
    assert nome_arquivo_para_cliente(origem) == (
        "apresentacao_completo_71e431d7_para_cliente.html"
    )
    html, _, _ = _html_completo_rede(tmp_path, estudo_id="anistia-d2")
    assert "data-arquivo-origem='apresentacao_completo.html'" in html or (
        "data-arquivo-origem=\"apresentacao_completo.html\"" in html
    )
    assert "rede-aviso-download" in html
    assert "_para_cliente.html" in html


def test_21_nome_download_com_nome_explicito(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    nome = "anistia_completo_cinco_abas.html"
    html = render_html_completo(
        vm,
        vm,
        vm,
        rede=doc,
        estudo_id=rascunho.id,
        nome_arquivo_html=nome,
    )
    cliente = nome_arquivo_para_cliente(nome)
    assert f"data-arquivo-origem='{nome}'" in html or f'data-arquivo-origem="{nome}"' in html
    assert cliente in html
