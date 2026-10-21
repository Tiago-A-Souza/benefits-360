"""Documento completo com aba Rede — HTML estático (pós-remoção do sandbox D2)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.presentation.rede_avisos import (
    AVISO_REDE_SEM_LOCALIZACAO,
    AVISO_REDE_SECAO_SEM_LOCALIZACAO,
)
from newport_app.services.rede_selecao import excluidos_rede, salvar_selecao_rede
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


def _html_completo_rede(tmp_path: Path, *, rascunho=None, cen_id=None):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    if rascunho is None:
        rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    doc = montar_rede_apresentacao(
        rascunho, [cen_id], excluidos=excluidos_rede(rascunho)
    )
    assert doc is not None
    html = render_html_completo(vm, vm, vm, rede=doc)
    return html, rascunho, cen_id, doc


def test_01_zero_script_no_documento_inteiro(tmp_path: Path):
    html, _, _, _ = _html_completo_rede(tmp_path)
    assert "<script" not in html.lower()


def test_02_sem_controles_sandbox_na_rede(tmp_path: Path):
    html, _, _, _ = _html_completo_rede(tmp_path)
    rede = html.split('id="visao-rede"', 1)[-1]
    assert "rede-sandbox-bar" not in rede
    assert "rede-btn-confirmar" not in rede
    assert "rede-btn-editar" not in rede
    assert "data-unlock" not in rede
    assert "newport-rede-state" not in rede
    assert "rede-sandbox-check" not in rede
    assert "rede-marcar-bloco" not in rede


def test_03_linhas_mantem_data_atributos(tmp_path: Path):
    html, _, _, doc = _html_completo_rede(tmp_path)
    ln = doc.secoes[0].paginas[0].blocos[0].linhas[0]
    assert f"data-rede-id='{ln.linha_id}'" in html or f'data-rede-id="{ln.linha_id}"' in html
    assert "data-municipio=" in html
    assert "data-zona=" in html
    assert "data-nome=" in html


def test_04_exclusao_etapa5_remove_prestador_do_html(tmp_path: Path):
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    lid = doc.secoes[0].paginas[0].blocos[0].linhas[0].linha_id
    salvar_selecao_rede(rascunho, [lid], revisada=True)
    html, _, _, _ = _html_completo_rede(tmp_path, rascunho=rascunho, cen_id=cen_id)
    assert f"data-rede-id='{lid}'" not in html and f'data-rede-id="{lid}"' not in html


def test_05_quatro_abas_anteriores_intactas(tmp_path: Path):
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    sem = render_html_completo(vm, vm, vm, rede=None)
    com = render_html_completo(
        vm, vm, vm, rede=montar_rede_apresentacao(rascunho, [cen_id])
    )
    extrair = lambda h: re.search(r'id="visao-resumo"[^>]*>(.*?)</section>', h, re.S).group(1)
    assert extrair(sem) == extrair(com)


def test_06_sem_localizacao_aviso_e_secao_sem_tabela(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    vidas = [v.model_copy(update={"uf": None, "cidade": None}) for v in rascunho.vidas]
    rasc = rascunho.model_copy(update={"vidas": vidas})
    html, _, _, doc = _html_completo_rede(tmp_path, rascunho=rasc, cen_id=cen_id)
    assert doc.aviso_sem_localizacao == AVISO_REDE_SEM_LOCALIZACAO
    rede = html.split('id="visao-rede"', 1)[1]
    assert "aviso-rede-localizacao" in rede
    assert "rede-secao-sem-localizacao" in rede
    assert AVISO_REDE_SECAO_SEM_LOCALIZACAO[:30] in html
    assert "class='tabela-rede" not in rede


def test_07_com_localizacao_tabela_estrutura_d1(tmp_path: Path):
    html, _, _, _ = _html_completo_rede(tmp_path)
    rede = html.split('id="visao-rede"', 1)[1]
    assert "secao-rede" in rede
    assert "class='tabela-rede" in rede
    assert "cont-rede" in rede
    assert "Cobertos" in rede


def test_08_nome_arquivo_gerado_sem_para_cliente(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    from newport_app.models.snapshot import GerarApresentacaoRequest
    from tests.test_fase2_tarefa2 import _aprovar, _stack

    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    rascunho = rascunho.model_copy(update={"id": "est-doc-estatico"})
    repo, _, snap_svc, apres = _stack(tmp_path, "doc-est")
    snap = _aprovar(repo, snap_svc, rascunho)
    res = apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(
            modo="completo",
            propostas_selecionadas=[cen_id],
            ressalvas=[],
        ),
    )
    assert "_para_cliente" not in res.caminho_relativo
    assert res.caminho_relativo.endswith(".html")
    assert re.search(r"apresentacao_completo_[a-f0-9]+\.html", res.caminho_relativo)
