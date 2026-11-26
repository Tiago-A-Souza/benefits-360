"""Simular Rede — consulta de laboratório (somente leitura, base da fase 1)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.presentation.rede_consulta import ConsultaRedeInvalida, LIMITE_SEM_FILTRO_GEOGRAFICO
from newport_app.repository.sqlite import SQLiteStudyRepository
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


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "simular-lab.db"


@pytest.fixture
def client(db_path: Path) -> TestClient:
    return TestClient(create_app(repo=SQLiteStudyRepository(db_path), seed_demos=False))


def _linhas(resp) -> list:
    return [ln for b in resp.blocos for ln in b.linhas]


def _linhas_json(resp: dict) -> list[dict]:
    return [ln for b in resp["blocos"] for ln in b["linhas"]]


def _hash_banco(db_path: Path) -> str:
    return hashlib.sha256(db_path.read_bytes()).hexdigest()


def _linhas_por_tabela(db_path: Path) -> dict[str, int]:
    with sqlite3.connect(db_path) as con:
        tabelas = [
            r[0]
            for r in con.execute(
                "select name from sqlite_master where type='table' "
                "and name not like 'sqlite_%'"
            )
        ]
        return {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in tabelas}


def _celulas(resp) -> list[str]:
    return [v for ln in _linhas(resp) for v in ln.celulas.values()]


def test_01_opcoes_vem_da_base_de_laboratorio():
    op = opcoes_simulacao_laboratorio()
    assert op.total_prestadores == 1455
    assert op.data_base_rede == "17/11/2026"
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
    r = consultar_por_laboratorio(
        "; ".join(MARCAS_SP_CAPITAL), uf="SP", municipio="SP.SAO PAULO"
    )
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


def test_02b_busca_vazia_e_recusada():
    with pytest.raises(ConsultaRedeInvalida):
        consultar_por_laboratorio()
    with pytest.raises(ConsultaRedeInvalida):
        consultar_por_laboratorio(" ; ")
    with pytest.raises(ConsultaRedeInvalida):
        consultar_por_laboratorio(todos=True)


def test_04_filtro_operadora_reduz_colunas():
    todas = consultar_por_laboratorio(
        "Delboni", uf="SP", municipio="SP.SAO PAULO"
    )
    amil = consultar_por_laboratorio(
        "Delboni", uf="SP", municipio="SP.SAO PAULO", operadoras=["Amil"]
    )
    assert amil.colunas
    assert len(amil.colunas) < len(todas.colunas)
    assert all(c.operadora == "Amil" for c in amil.colunas)


def test_05_cobertura_binaria_nunca_codigo_de_exame():
    r = consultar_por_laboratorio("Delboni", uf="SP", municipio="SP.SAO PAULO")
    valores = set(_celulas(r))
    assert valores <= {MARCA_COBERTURA}
    assert MARCA_COBERTURA == MARCA_COBERTURA_ETAPA5 == "✓"
    assert r.contagem_por_coluna
    for chave, n in r.contagem_por_coluna.items():
        assert 0 < n <= r.total_linhas
        assert any(c.chave == chave for c in r.colunas)


def test_06_ver_todos_lista_prestador_sem_agrupar():
    marcas = consultar_por_laboratorio("LAB", uf="SP", municipio="SP.SAO PAULO")
    todos = consultar_por_laboratorio("LAB", uf="SP", municipio="SP.SAO PAULO", todos=True)
    assert todos.mostrando_todos is True
    assert marcas.mostrando_todos is False
    assert todos.total_linhas > marcas.total_linhas
    ids = [ln.linha_id for ln in _linhas(todos)]
    assert all(i.startswith("l") for i in ids)
    assert len(ids) == len(set(ids))
    assert {v for v in _celulas(todos)} <= {MARCA_COBERTURA}


def test_07_trava_100_sem_filtro_geografico():
    r = consultar_por_laboratorio("LAB", todos=True)
    assert r.requer_confirmacao is True
    assert r.total_linhas == 0
    assert r.total_encontrado > LIMITE_SEM_FILTRO_GEOGRAFICO
    ok = consultar_por_laboratorio("LAB", todos=True, confirmar=True)
    assert ok.requer_confirmacao is False
    assert ok.total_linhas == ok.total_encontrado > LIMITE_SEM_FILTRO_GEOGRAFICO


def test_08_aviso_porto_fora_de_sp_rj_df():
    ba = consultar_por_laboratorio(
        "Delboni", uf="BA", municipio="BA.SALVADOR", operadoras=["Porto Seguro"]
    )
    assert ba.aviso_porto == AVISO_PORTO_MEDSERVICE
    sp = consultar_por_laboratorio(
        "Delboni", uf="SP", municipio="SP.SAO PAULO", operadoras=["Porto Seguro"]
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
    consultar_por_laboratorio("Delboni", uf="SP")
    consultar_por_plano_laboratorio(
        opcoes_simulacao_laboratorio().operadoras[0].planos[0].chave, uf="RJ"
    )
    assert not alvo.exists()


# --- Rotas HTTP (somente leitura, demo sem auth) ----------------------------


def test_api_01_opcoes_laboratorio(client: TestClient):
    r = client.get("/api/simular-rede/laboratorios/opcoes")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total_prestadores"] == 1455
    assert corpo["data_base_rede"] == "17/11/2026"
    assert corpo["total_principais"] == 10
    sp = next(u for u in corpo["ufs"] if u["uf"] == "SP")
    assert "SP.FRANCISCO MORATO" in {m["chave"] for m in sp["municipios"]}
    assert all(m["zonas"] == [] for u in corpo["ufs"] for m in u["municipios"])


def test_api_02_por_laboratorio_sp_capital(client: TestClient):
    r = client.get(
        "/api/simular-rede/laboratorios/por-laboratorio",
        params={"q": "Delboni", "uf": "SP", "municipio": "SP.SAO PAULO"},
    )
    assert r.status_code == 200
    corpo = r.json()
    nomes = {ln["prestador"] for ln in _linhas_json(corpo)}
    assert nomes == {"Delboni"}
    assert corpo["contagem_por_coluna"]
    assert corpo["aviso_porto"] is None
    valores = {v for ln in _linhas_json(corpo) for v in ln["celulas"].values()}
    assert valores <= {MARCA_COBERTURA}


def test_api_03_busca_varios_termos_e_operadora(client: TestClient):
    r = client.get(
        "/api/simular-rede/laboratorios/por-laboratorio",
        params=[
            ("q", "Delbôni"),
            ("q", "Lavoisier"),
            ("uf", "SP"),
            ("municipio", "SP.SAO PAULO"),
            ("operadoras", "Amil"),
        ],
    ).json()
    assert {ln["prestador"] for ln in _linhas_json(r)} == {"Delboni", "Lavoisier"}
    assert r["colunas"] and all(c["operadora"] == "Amil" for c in r["colunas"])


def test_api_04_por_plano_rio(client: TestClient):
    op = client.get("/api/simular-rede/laboratorios/opcoes").json()
    plano = next(
        pl["chave"] for o in op["operadoras"] if o["nome"] == "Amil" for pl in o["planos"]
    )
    r = client.get(
        "/api/simular-rede/laboratorios/por-plano",
        params={"plano": plano, "uf": "RJ", "municipio": "RJ.RIO DE JANEIRO"},
    )
    assert r.status_code == 200
    corpo = r.json()
    nomes = {ln["prestador"] for ln in _linhas_json(corpo)}
    assert nomes and nomes <= MARCAS_RIO
    assert [c["chave"] for c in corpo["colunas"]] == [plano]


def test_api_05_ver_todos_trava_100_e_confirma(client: TestClient):
    vazio = client.get("/api/simular-rede/laboratorios/por-laboratorio")
    assert vazio.status_code == 422
    assert client.get(
        "/api/simular-rede/laboratorios/por-laboratorio", params={"todos": True}
    ).status_code == 422
    r = client.get(
        "/api/simular-rede/laboratorios/por-laboratorio",
        params={"q": "LAB", "todos": True},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["requer_confirmacao"] is True
    assert corpo["total_linhas"] == 0
    ok = client.get(
        "/api/simular-rede/laboratorios/por-laboratorio",
        params={"q": "LAB", "todos": True, "confirmar": True},
    ).json()
    assert ok["requer_confirmacao"] is False
    assert ok["total_linhas"] > LIMITE_SEM_FILTRO_GEOGRAFICO


def test_api_06_aviso_porto_e_plano_inexistente(client: TestClient):
    r = client.get(
        "/api/simular-rede/laboratorios/por-laboratorio",
        params={
            "q": "Delboni",
            "uf": "BA",
            "municipio": "BA.SALVADOR",
            "operadoras": "Porto Seguro",
        },
    ).json()
    assert r["aviso_porto"] == AVISO_PORTO_MEDSERVICE
    bad = client.get("/api/simular-rede/laboratorios/por-plano", params={"plano": "999999"})
    assert bad.status_code == 422


def test_api_07_nada_e_gravado(client: TestClient, db_path: Path):
    client.get("/api/estudos")
    antes = _hash_banco(db_path)
    contagem = _linhas_por_tabela(db_path)
    client.get("/api/simular-rede/laboratorios/opcoes")
    client.get(
        "/api/simular-rede/laboratorios/por-laboratorio",
        params={"q": "Delboni", "uf": "SP", "municipio": "SP.SAO PAULO"},
    )
    plano = client.get("/api/simular-rede/laboratorios/opcoes").json()["operadoras"][0][
        "planos"
    ][0]
    client.get(
        "/api/simular-rede/laboratorios/por-plano",
        params={"plano": plano["chave"], "uf": "RJ"},
    )
    assert client.get("/api/estudos").json() == []
    assert _linhas_por_tabela(db_path) == contagem
    assert _hash_banco(db_path) == antes


def test_api_08_rotas_de_hospital_seguem_iguais(client: TestClient):
    hosp = client.get("/api/simular-rede/opcoes").json()
    lab = client.get("/api/simular-rede/laboratorios/opcoes").json()
    sp_h = next(u for u in hosp["ufs"] if u["uf"] == "SP")
    sp_l = next(u for u in lab["ufs"] if u["uf"] == "SP")
    assert any(m["zonas"] for m in sp_h["municipios"])
    assert all(m["zonas"] == [] for m in sp_l["municipios"])
    assert "SP.FRANCISCO MORATO" not in {m["chave"] for m in sp_h["municipios"]}
    assert "SP.FRANCISCO MORATO" in {m["chave"] for m in sp_l["municipios"]}
