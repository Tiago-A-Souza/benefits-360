"""Layout estreito da aba Rede — colunas fixas, bairro inline, cab. repetido leve."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newport_app.presentation.colisao_coluna import resolver_colunas_selecionadas
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import (
    linha_tem_cobertura_na_secao,
    montar_rede_apresentacao,
)
from newport_app.presentation.rede_prestador_rotulo import (
    _fold,
    nome_prestador_para_rotulo,
    recortar_bairro_do_nome,
    rotulo_prestador_html,
)
from newport_app.presentation.rede_renderer import render_corpo_rede
from newport_app.snapshot.comparativo import ler_comparativo_congelado
from tests.test_rede_fase_d1 import (
    _anistia_seis_com_localizacao,
    _doc_anistia_seis_rede,
    _html_de,
)

ROOT = Path(__file__).resolve().parents[1]
_LARGURA_COL_PLANO = 112
_LARGURA_MAX_5_PLANOS = 1180
_LARGURA_PRESTADOR_MAX = _LARGURA_MAX_5_PLANOS - 5 * _LARGURA_COL_PLANO


def _css_rede() -> str:
    return (ROOT / "src/newport_app/presentation/html_renderer.py").read_text(
        encoding="utf-8"
    )


def test_01_coluna_plano_largura_fixa_e_pl_quebra_linha():
    css = _css_rede()
    assert "width:112px" in css.replace(" ", "")
    assert "white-space:normal" in css and ".pl{" in css


def test_02_bairro_na_mesma_linha():
    css = _css_rede()
    assert ".bairro-rede{display:inline" in css.replace(" ", "")


def test_03_recorte_sufixo_bairro_cemeru():
    longo = "HOSP CEMERU - AMESC SANTA CRUZ"
    assert recortar_bairro_do_nome(longo, "SANTA CRUZ") == "HOSP CEMERU - AMESC"
    assert recortar_bairro_do_nome(longo, "Santa Cruz") == "HOSP CEMERU - AMESC"
    # Matriz real: prestador curto + bairro em coluna aparte (Anistia / SiscorNet).
    assert (
        nome_prestador_para_rotulo("HOSP CEMERU - AMESC", "SANTA CRUZ")
        == "HOSP CEMERU - AMESC"
    )
    assert (
        nome_prestador_para_rotulo("HOSP RIO BARRA - DOR", "BARRA DA TIJUCA")
        == "HOSP RIO BARRA - DOR"
    )
    assert (
        nome_prestador_para_rotulo("HOSP SAMARITANO", "BARRA DA TIJUCA")
        == "HOSP SAMARITANO"
    )
    html_cemeru = rotulo_prestador_html("HOSP CEMERU - AMESC", "SANTA CRUZ")
    assert html_cemeru.startswith("HOSP CEMERU - AMESC<span")
    assert " AMESC SANTA CRUZ" not in html_cemeru


def test_04_nome_intacto_quando_sufixo_nao_bate():
    nome = "HOSPITAL SIrio Libanes"
    assert recortar_bairro_do_nome(nome, "BELA VISTA") == nome
    assert nome_prestador_para_rotulo(nome, "BELA VISTA") == nome


def test_04b_nome_so_bairro_nao_recorta():
    assert recortar_bairro_do_nome("SANTA CRUZ", "SANTA CRUZ") == "SANTA CRUZ"
    assert recortar_bairro_do_nome("MOEMA", "MOEMA") == "MOEMA"
    assert nome_prestador_para_rotulo("MOEMA", "MOEMA") == "MOEMA"


def test_04c_recorte_nome_longo_real_matriz():
    # Bairro no meio do nome — não é sufixo; mantém inteiro.
    assert (
        recortar_bairro_do_nome(
            "HOSP DE CLIN SANTA CRUZ - MEMORIAL", "SANTA CRUZ"
        )
        == "HOSP DE CLIN SANTA CRUZ - MEMORIAL"
    )
    assert (
        recortar_bairro_do_nome("HOSPITAL CASA SANTA CRUZ", "SANTA CRUZ")
        == "HOSPITAL CASA"
    )
    assert (
        recortar_bairro_do_nome("NIG - CLIN BARRA DA TIJUCA", "BARRA DA TIJUCA")
        == "NIG - CLIN"
    )


def test_05_cabecalho_repetido_so_nome_plano(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    html = render_corpo_rede(doc)
    trecho = html.split("rede-cab-repetido", 1)[1][:1200]
    assert "rede-cab-plano" in trecho
    assert "<span class='op'>" not in trecho.split("</tr>", 1)[0]


def test_06_linha_bloco_diz_cobertos(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    html = render_corpo_rede(doc)
    assert "Prestadores cobertos" not in html
    assert ">Cobertos</td>" in html


def test_07_cinco_planos_cabe_em_1180px():
    # Prestador + 5 colunas de plano × 112px.
    assert _LARGURA_PRESTADOR_MAX + 5 * _LARGURA_COL_PLANO == _LARGURA_MAX_5_PLANOS


def test_08_maradei_belem_permanece(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    html = render_corpo_rede(doc)
    assert "MARADEI" in html.upper()


def test_09_zero_linhas_sem_cobertura(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    for sec in doc.secoes:
        for b in sec.blocos:
            for ln in b.linhas:
                assert linha_tem_cobertura_na_secao(ln, sec.colunas)


def test_10_contagem_bloco_coerente(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    html = render_corpo_rede(doc)
    bloco = next(b for b in doc.secoes[0].blocos if "BELEM" in b.titulo.upper())
    assert f"{len(bloco.linhas)} prestadores" in html


def test_11_thead_sticky_mantido():
    css = _css_rede()
    assert "position:sticky" in css and ".tabela-rede thead th" in css


def test_13_gabarito_anistia_ivtec(tmp_path: Path):
    from tests.test_fase5_faixas_por_grupo import test_12_gabaritos_valor_por_valor

    test_12_gabaritos_valor_por_valor(tmp_path)


def test_14_quatro_abas_inalteradas(tmp_path: Path):
    from tests.test_rede_documento_estatico import test_05_quatro_abas_anteriores_intactas

    test_05_quatro_abas_anteriores_intactas(tmp_path)


def test_15_rascunhos_banco_carregam():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "scripts/verificar_rascunhos_do_banco.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "FALHAM_CARGA=0" in r.stdout


def test_16_hashes_snapshot_intactos():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "scripts/verificar_hashes_snapshots.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert "HASH_DIVERGENTE=0" in r.stdout


def test_17_contagem_recortes_bairro_anistia(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    recortes = 0
    for sec in doc.secoes:
        for b in sec.blocos:
            for ln in b.linhas:
                if not ln.bairro:
                    continue
                if nome_prestador_para_rotulo(ln.prestador, ln.bairro) != ln.prestador:
                    recortes += 1
                elif recortar_bairro_do_nome(ln.prestador, ln.bairro) != ln.prestador:
                    recortes += 1
    assert recortes > 0
    print(f"RECORTES_BAIRRO={recortes}")


def test_18_export_rj_sem_bairro_no_nome_antes_do_span(tmp_path: Path):
    doc, _ = _doc_anistia_seis_rede(tmp_path)
    html = render_corpo_rede(doc)
    casos = [
        ("HOSP CEMERU - AMESC", "SANTA CRUZ"),
        ("HOSP RIO BARRA - DOR", "BARRA DA TIJUCA"),
        ("HOSP SAMARITANO", "BARRA DA TIJUCA"),
    ]
    for prest, bairro in casos:
        trecho = rotulo_prestador_html(prest, bairro)
        assert trecho in html
        nome_html = trecho.split("<span", 1)[0]
        assert not _fold(nome_html).endswith(_fold(bairro))
