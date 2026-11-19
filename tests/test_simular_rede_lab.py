"""Simular Rede — consulta de laboratório (somente leitura, base da fase 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.presentation.rede_consulta import ConsultaRedeInvalida, LIMITE_SEM_FILTRO_GEOGRAFICO
from newport_app.presentation.rede_consulta_lab import (
    AVISO_PORTO_MEDSERVICE,
    MARCA_COBERTURA,
    consultar_por_laboratorio,
    consultar_por_plano_laboratorio,
    opcoes_simulacao_laboratorio,
)
from newport_app.presentation.rede_labs import MARCA_COBERTURA as MARCA_COBERTURA_ETAPA5
from newport_app.presentation.rede_matriz_hospital import CAMINHO_XLSX_PADRAO
from newport_app.presentation.rede_matriz_laboratorio import limpar_cache_base_rede_laboratorio

pytestmark = pytest.mark.skipif(
    not CAMINHO_XLSX_PADRAO.is_file(),
    reason="planilha SiscorNet ausente",
)

MARCAS_SP_CAPITAL = {
    "Delboni",
    "Lavoisier",
    "CDB",
    "Femme",
    "Pardini",
    "Salomão",
    "A+ Medicina Diagnóstica",
}
MARCAS_RIO = {
    "Pardini",
    "A+ Medicina Diagnóstica",
    "Bittar",
    "Lamina",
    "Bronstein",
}


@pytest.fixture(scope="module", autouse=True)
def _cache_lab():
    limpar_cache_base_rede_laboratorio()
    yield


def _linhas(resp) -> list:
    return [ln for b in resp.blocos for ln in b.linhas]


def _celulas(resp) -> list[str]:
    return [v for ln in _linhas(resp) for v in ln.celulas.values()]


def test_01_opcoes_vem_da_base_de_laboratorio():
    op = opcoes_simulacao_laboratorio()
    assert op.total_prestadores >= 2600
    assert op.total_principais == 10
    assert op.operadoras
    ufs = {u.uf for u in op.ufs}
    assert {"SP", "RJ", "BA"} <= ufs
    sp = next(u for u in op.ufs if u.uf == "SP")
    chaves = {m.chave for m in sp.municipios}
    assert "SP.SAO PAULO" in chaves
    assert "SP.FRANCISCO MORATO" in chaves
    assert all(m.zonas == [] for u in op.ufs for m in u.municipios)


def test_02_sp_capital_agrupa_marcas_e_lista_municipio():
    r = consultar_por_laboratorio(uf="SP", municipio="SP.SAO PAULO")
    nomes = {ln.prestador for ln in _linhas(r)}
    assert nomes == MARCAS_SP_CAPITAL
    assert r.total_linhas == 7
    assert r.total_encontrado == 7
    assert r.ocultos_nao_principais > 0
    assert r.data_base_rede
    assert r.mostrando_todos is False
    for ln in _linhas(r):
        assert ln.principal is True
        assert "Sao Paulo" in ln.municipios
        assert ln.linha_id.startswith("marca:")


def test_03_busca_acento_insensivel_e_varios_termos():
    um = consultar_por_laboratorio("Delbôni", uf="SP", municipio="SP.SAO PAULO")
    assert {ln.prestador for ln in _linhas(um)} == {"Delboni"}
    dois = consultar_por_laboratorio(
        "Delboni; Lavoisier", uf="SP", municipio="SP.SAO PAULO"
    )
    assert {ln.prestador for ln in _linhas(dois)} == {"Delboni", "Lavoisier"}
    virgula = consultar_por_laboratorio(
        "femme, pardini", uf="SP", municipio="SP.SAO PAULO"
    )
    assert {ln.prestador for ln in _linhas(virgula)} == {"Femme", "Pardini"}


def test_04_filtro_operadora_reduz_colunas():
    todas = consultar_por_laboratorio(uf="SP", municipio="SP.SAO PAULO")
    amil = consultar_por_laboratorio(
        uf="SP", municipio="SP.SAO PAULO", operadoras=["Amil"]
    )
    assert amil.colunas
    assert len(amil.colunas) < len(todas.colunas)
    assert all(c.operadora == "Amil" for c in amil.colunas)


def test_05_cobertura_binaria_nunca_codigo_de_exame():
    r = consultar_por_laboratorio(uf="SP", municipio="SP.SAO PAULO")
    valores = set(_celulas(r))
    assert valores <= {MARCA_COBERTURA}
    assert MARCA_COBERTURA == MARCA_COBERTURA_ETAPA5 == "✓"
    assert r.contagem_por_coluna
    for chave, n in r.contagem_por_coluna.items():
        assert 0 < n <= r.total_linhas
        assert any(c.chave == chave for c in r.colunas)


def test_06_ver_todos_lista_prestador_sem_agrupar():
    marcas = consultar_por_laboratorio(uf="SP", municipio="SP.SAO PAULO")
    todos = consultar_por_laboratorio(uf="SP", municipio="SP.SAO PAULO", todos=True)
    assert todos.mostrando_todos is True
    assert todos.total_linhas > marcas.total_linhas
    assert todos.total_linhas > 50
    ids = [ln.linha_id for ln in _linhas(todos)]
    assert all(i.startswith("l") for i in ids)
    assert len(ids) == len(set(ids))
    assert {v for v in _celulas(todos)} <= {MARCA_COBERTURA}


def test_07_trava_100_sem_filtro_geografico():
    r = consultar_por_laboratorio(todos=True)
    assert r.requer_confirmacao is True
    assert r.total_linhas == 0
    assert r.total_encontrado > LIMITE_SEM_FILTRO_GEOGRAFICO
    ok = consultar_por_laboratorio(todos=True, confirmar=True)
    assert ok.requer_confirmacao is False
    assert ok.total_linhas == ok.total_encontrado > LIMITE_SEM_FILTRO_GEOGRAFICO


def test_08_aviso_porto_fora_de_sp_rj_df():
    ba = consultar_por_laboratorio(
        uf="BA", municipio="BA.SALVADOR", operadoras=["Porto Seguro"]
    )
    assert ba.aviso_porto == AVISO_PORTO_MEDSERVICE
    sp = consultar_por_laboratorio(
        uf="SP", municipio="SP.SAO PAULO", operadoras=["Porto Seguro"]
    )
    assert sp.aviso_porto is None


def test_09_por_plano_rio_traz_marcas_cobertas():
    op = opcoes_simulacao_laboratorio()
    plano = next(
        pl.chave
        for o in op.operadoras
        if o.nome == "Amil"
        for pl in o.planos
    )
    r = consultar_por_plano_laboratorio(plano, uf="RJ", municipio="RJ.RIO DE JANEIRO")
    nomes = {ln.prestador for ln in _linhas(r)}
    assert nomes
    assert nomes <= MARCAS_RIO
    assert r.total_linhas == len(nomes)
    assert r.contagem_por_coluna
    for ln in _linhas(r):
        assert ln.celulas
        assert set(ln.celulas.values()) <= {MARCA_COBERTURA}
        assert "Rio De Janeiro" in ln.municipios


def test_10_por_plano_inexistente_levanta():
    with pytest.raises(ConsultaRedeInvalida):
        consultar_por_plano_laboratorio("nao-existe")


def test_11_por_plano_ver_todos_trava_sem_geo():
    op = opcoes_simulacao_laboratorio()
    plano = op.operadoras[0].planos[0].chave
    r = consultar_por_plano_laboratorio(plano, todos=True)
    if r.total_encontrado > LIMITE_SEM_FILTRO_GEOGRAFICO:
        assert r.requer_confirmacao is True
        assert r.total_linhas == 0
        ok = consultar_por_plano_laboratorio(plano, todos=True, confirmar=True)
        assert ok.total_linhas > LIMITE_SEM_FILTRO_GEOGRAFICO
    else:
        assert r.requer_confirmacao is False


def test_12_consulta_nao_grava_e_nao_depende_de_estudo(tmp_path: Path):
    alvo = tmp_path / "vazio.db"
    consultar_por_laboratorio(uf="SP")
    consultar_por_plano_laboratorio(
        opcoes_simulacao_laboratorio().operadoras[0].planos[0].chave, uf="RJ"
    )
    assert not alvo.exists()
