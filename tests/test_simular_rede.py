"""Simular Rede — consulta da rede credenciada fora de qualquer estudo.

Cobre: acesso sem estudo e sem gravação, busca por hospital, consulta por plano,
filtros, principais, rede verticalizada e cache em memória da planilha.
"""

from __future__ import annotations

import functools
import hashlib
import os
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.presentation import rede_consulta as rc
from newport_app.presentation.rede_matriz_hospital import (
    CAMINHO_XLSX_PADRAO,
    carregar_base_rede_hospital,
    limpar_cache_base_rede_hospital,
)
from newport_app.repository.sqlite import SQLiteStudyRepository

pytestmark = pytest.mark.skipif(
    not CAMINHO_XLSX_PADRAO.is_file(),
    reason="planilha SiscorNet ausente",
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "simular.db"


@pytest.fixture
def client(db_path: Path) -> TestClient:
    return TestClient(create_app(repo=SQLiteStudyRepository(db_path), seed_demos=False))


def _linhas(resp: dict) -> list[dict]:
    return [ln for b in resp["blocos"] for ln in b["linhas"]]


def _hash_banco(db_path: Path) -> str:
    return hashlib.sha256(db_path.read_bytes()).hexdigest()


@functools.cache
def _chave_plano_mais_cobertura() -> str:
    """Chave do plano que mais lista prestadores principais."""
    melhor, maior = "", -1
    for op in rc.opcoes_simulacao().operadoras:
        for pl in op.planos:
            n = rc.consultar_por_plano(pl.chave, confirmar=True).total_linhas
            if n > maior:
                melhor, maior = pl.chave, n
    return melhor


def _plano_com_mais_cobertura(client: TestClient) -> str:
    return _chave_plano_mais_cobertura()


# --- Acesso ----------------------------------------------------------------


def test_01_abre_sem_estudo_nenhum(client: TestClient):
    assert client.get("/api/estudos").json() == []
    r = client.get("/api/simular-rede/opcoes")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total_prestadores"] == 882
    assert corpo["data_base_rede"] == "17/11/2026"
    assert corpo["operadoras"] and corpo["ufs"]


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


def test_02_nada_e_gravado(client: TestClient, db_path: Path):
    client.get("/api/estudos")  # força criação do esquema
    antes = _hash_banco(db_path)
    contagem = _linhas_por_tabela(db_path)
    client.get("/api/simular-rede/opcoes")
    client.get("/api/simular-rede/por-hospital", params={"q": "Samaritano"})
    plano = client.get("/api/simular-rede/opcoes").json()["operadoras"][0]["planos"][0]
    client.get("/api/simular-rede/por-plano", params={"plano": plano["chave"], "uf": "RJ"})
    assert client.get("/api/estudos").json() == []
    assert _linhas_por_tabela(db_path) == contagem
    assert contagem["rascunhos"] == 0 and contagem["estudos_meta"] == 0
    assert _hash_banco(db_path) == antes


# --- Por hospital -----------------------------------------------------------


def test_03_samaritano_traz_barra_e_botafogo_em_linhas_separadas(client: TestClient):
    r = client.get(
        "/api/simular-rede/por-hospital", params={"q": "Samaritano", "uf": "RJ"}
    ).json()
    linhas = _linhas(r)
    bairros = {ln["bairro"] for ln in linhas}
    assert {"BARRA DA TIJUCA", "BOTAFOGO"} <= bairros
    barra = next(ln for ln in linhas if ln["bairro"] == "BARRA DA TIJUCA")
    botafogo = next(ln for ln in linhas if ln["bairro"] == "BOTAFOGO")
    assert barra["linha_id"] != botafogo["linha_id"]


def test_03b_busca_ignora_acento_hifen_e_palavra_generica(client: TestClient):
    r = client.get(
        "/api/simular-rede/por-hospital",
        params={"q": ["Hospital Sírio-Libanês", "einstein"]},
    ).json()
    nomes = {ln["prestador"] for ln in _linhas(r)}
    assert any("SIRIO" in n for n in nomes)
    assert any("EINSTEIN" in n for n in nomes)


def test_04_uma_coluna_por_plano_com_codigo_de_cobertura(client: TestClient):
    r = client.get(
        "/api/simular-rede/por-hospital", params={"q": "Samaritano", "uf": "RJ"}
    ).json()
    assert len(r["colunas"]) > 1
    chaves = {c["chave"] for c in r["colunas"]}
    codigos = {v for ln in _linhas(r) for v in ln["celulas"].values()}
    assert codigos and codigos <= {"H", "HD", "M", "PS", "H PS", "H HD", "H M", "H HD PS",
                                   "H M PS", "H HD M", "H HD M PS", "HD PS", "M PS", "HD M",
                                   "HD M PS"}
    for ln in _linhas(r):
        assert set(ln["celulas"]) <= chaves
    assert all({"operadora", "plano"} <= set(c) for c in r["colunas"])


def test_05_hospital_sem_cobertura_aparece_com_linha_vazia():
    base = carregar_base_rede_hospital()
    from newport_app.presentation.rede_especialidade import (
        prestador_passa_filtro_especialidade,
    )

    sem = next(
        p for p in base.prestadores if not prestador_passa_filtro_especialidade(p.celulas)
    )
    r = rc.consultar_por_hospital(
        sem.prestador, uf=sem.uf, municipio=sem.chave_municipio, todos=True
    )
    achados = [ln for b in r.blocos for ln in b.linhas if ln.prestador == sem.prestador]
    assert achados, "hospital sem cobertura não pode sumir"
    assert all(not ln.celulas for ln in achados if ln.bairro == (sem.bairro or ""))


def test_05b_busca_vazia_e_recusada(client: TestClient):
    assert client.get("/api/simular-rede/por-hospital").status_code == 422
    assert client.get("/api/simular-rede/por-hospital", params={"q": " ; "}).status_code == 422


def test_05c_einstein_lista_unidades_sem_restringir_a_alice(client: TestClient):
    r = client.get("/api/simular-rede/por-hospital", params={"q": "Einstein"}).json()
    linhas = _linhas(r)
    assert linhas and all("EINSTEIN" in ln["prestador"].upper() for ln in linhas)
    ops = {c["operadora"] for c in r["colunas"]}
    assert len(ops) > 1
    assert "Alice" in ops


# --- Por plano --------------------------------------------------------------


def test_06_escolher_plano_lista_prestadores_cobertos_por_ele(client: TestClient):
    opcoes = client.get("/api/simular-rede/opcoes").json()
    op = next(o for o in opcoes["operadoras"] if o["nome"] == "Porto Seguro")
    chave = op["planos"][0]["chave"]
    r = client.get(
        "/api/simular-rede/por-plano", params={"plano": chave, "confirmar": True}
    ).json()
    assert r["total_linhas"] > 0
    assert [c["chave"] for c in r["colunas"]] == [chave]
    for ln in _linhas(r):
        assert chave in ln["celulas"] and ln["celulas"][chave]


def test_06b_plano_inexistente_e_recusado(client: TestClient):
    r = client.get("/api/simular-rede/por-plano", params={"plano": "999999"})
    assert r.status_code == 422


def test_07_agrupa_por_municipio_com_zona_em_sp_e_rj(client: TestClient):
    plano = _plano_com_mais_cobertura(client)
    r = client.get(
        "/api/simular-rede/por-plano", params={"plano": plano, "confirmar": True}
    ).json()
    municipios = [b["municipio"] for b in r["blocos"]]
    assert len(municipios) == len(set(municipios)) > 1
    assert municipios[0] in {"SP.SAO PAULO", "RJ.RIO DE JANEIRO"}  # capitais primeiro
    for b in r["blocos"]:
        assert {ln["municipio"] for ln in b["linhas"]} == {b["municipio"]}
    capitais = [
        ln
        for b in r["blocos"]
        if b["municipio"] in {"SP.SAO PAULO", "RJ.RIO DE JANEIRO"}
        for ln in b["linhas"]
    ]
    assert any(ln["zona_sigla"] for ln in capitais)


def test_08_sem_filtro_geografico_avisa_o_volume_antes_de_listar(client: TestClient):
    plano = _plano_com_mais_cobertura(client)
    r = client.get("/api/simular-rede/por-plano", params={"plano": plano}).json()
    assert r["requer_confirmacao"] is True
    assert r["total_linhas"] == 0 and r["blocos"] == []
    assert r["total_encontrado"] > rc.LIMITE_SEM_FILTRO_GEOGRAFICO
    assert str(r["total_encontrado"] - r["ocultos_nao_principais"]) in r["aviso"]
    confirmado = client.get(
        "/api/simular-rede/por-plano", params={"plano": plano, "confirmar": True}
    ).json()
    assert confirmado["requer_confirmacao"] is False
    assert confirmado["total_linhas"] > rc.LIMITE_SEM_FILTRO_GEOGRAFICO
    filtrado = client.get(
        "/api/simular-rede/por-plano", params={"plano": plano, "uf": "SP"}
    ).json()
    assert filtrado["requer_confirmacao"] is False


# --- Filtros e marcação -----------------------------------------------------


def test_09_filtros_de_estado_municipio_e_zona_reduzem_nos_dois_modos(client: TestClient):
    plano = _plano_com_mais_cobertura(client)
    base = {"plano": plano, "confirmar": True}
    total = client.get("/api/simular-rede/por-plano", params=base).json()["total_linhas"]
    uf = client.get("/api/simular-rede/por-plano", params={**base, "uf": "SP"}).json()
    mun = client.get(
        "/api/simular-rede/por-plano",
        params={**base, "uf": "SP", "municipio": "SP.SAO PAULO"},
    ).json()
    zona = client.get(
        "/api/simular-rede/por-plano",
        params={**base, "uf": "SP", "municipio": "SP.SAO PAULO", "zona": "ZONA SUL"},
    ).json()
    assert total > uf["total_linhas"] > mun["total_linhas"] > zona["total_linhas"] > 0
    assert {ln["zona"] for ln in _linhas(zona)} == {"ZONA SUL"}
    assert {ln["municipio"] for ln in _linhas(mun)} == {"SP.SAO PAULO"}

    h = {"q": "hospital"}
    h_total = client.get("/api/simular-rede/por-hospital", params=h).json()["total_linhas"]
    h_uf = client.get("/api/simular-rede/por-hospital", params={**h, "uf": "RJ"}).json()
    h_mun = client.get(
        "/api/simular-rede/por-hospital",
        params={**h, "uf": "RJ", "municipio": "RJ.RIO DE JANEIRO"},
    ).json()
    assert h_total > h_uf["total_linhas"] >= h_mun["total_linhas"] > 0
    assert {ln["municipio"] for ln in _linhas(h_uf)} == {
        b["municipio"] for b in h_uf["blocos"]
    }
    assert all(ln["municipio"].startswith("RJ.") for ln in _linhas(h_uf))


def test_10_so_principais_por_padrao_e_ver_todos_amplia(client: TestClient):
    # Samaritano na extração 17/11 só restou como principal; usa recorte com mistos.
    params = {"q": "hospital", "uf": "SP", "municipio": "SP.SAO PAULO"}
    padrao = client.get("/api/simular-rede/por-hospital", params=params).json()
    todos = client.get(
        "/api/simular-rede/por-hospital", params={**params, "todos": True}
    ).json()
    assert all(ln["principal"] for ln in _linhas(padrao))
    assert padrao["ocultos_nao_principais"] > 0
    assert todos["total_linhas"] == padrao["total_linhas"] + padrao["ocultos_nao_principais"]
    assert any(not ln["principal"] for ln in _linhas(todos))
    assert todos["mostrando_todos"] is True and todos["ocultos_nao_principais"] == 0


def test_11_prestador_verticalizado_vem_marcado_e_so_cobre_a_propria_operadora(
    client: TestClient,
):
    por_op = {
        c["chave"]: c["operadora"]
        for o in client.get("/api/simular-rede/opcoes").json()["operadoras"]
        for p in o["planos"]
        for c in [{"chave": p["chave"], "operadora": o["nome"]}]
    }
    r = client.get(
        "/api/simular-rede/por-hospital",
        params={"q": "hospital", "todos": True},
    ).json()
    from newport_app.presentation.rede_visao import operadoras_rede_verticalizada

    verticais = [ln for ln in _linhas(r) if ln["rede_verticalizada"]]
    assert verticais, "a base tem 59 prestadores de rede própria"
    # Marcação visível: o texto do CSV acompanha a linha.
    assert {"Unimed", "Hapvida"} <= {ln["rede_verticalizada"] for ln in verticais}
    # Regra do pipeline: onde a operadora dona é reconhecida, só ela cobre.
    verificadas = 0
    for ln in verticais:
        donas = operadoras_rede_verticalizada(ln["rede_verticalizada"])
        if not donas or not ln["celulas"]:
            continue
        verificadas += 1
        assert {por_op[ch] for ch in ln["celulas"]} <= donas, (
            "verticalizado não aparece coberto em plano de outra operadora"
        )
    assert verificadas >= 5
    unimed = [ln for ln in verticais if ln["rede_verticalizada"] == "Unimed"]
    assert unimed and all(
        {por_op[ch] for ch in ln["celulas"]} == {"Seguros Unimed"} for ln in unimed
    )


# --- Desempenho / cache -----------------------------------------------------


@pytest.fixture
def contador_leituras_excel(monkeypatch):
    import openpyxl

    chamadas = {"n": 0}
    original = openpyxl.load_workbook

    def contando(*a, **k):
        chamadas["n"] += 1
        return original(*a, **k)

    monkeypatch.setattr(openpyxl, "load_workbook", contando)
    return chamadas


def test_12_segunda_consulta_nao_rele_a_planilha(contador_leituras_excel):
    limpar_cache_base_rede_hospital()
    rc.consultar_por_hospital("Samaritano")
    primeira = contador_leituras_excel["n"]
    assert primeira >= 1
    rc.consultar_por_hospital("Einstein", uf="SP")
    rc.consultar_por_plano(rc.opcoes_simulacao().operadoras[0].planos[0].chave, uf="SP")
    assert contador_leituras_excel["n"] == primeira


def test_12b_etapa5_e_exportacao_tambem_reaproveitam_o_cache(contador_leituras_excel):
    limpar_cache_base_rede_hospital()
    a = carregar_base_rede_hospital()
    lidas = contador_leituras_excel["n"]
    b = carregar_base_rede_hospital()
    assert b is a
    assert contador_leituras_excel["n"] == lidas


def test_13_alterar_a_planilha_invalida_o_cache(tmp_path: Path, contador_leituras_excel):
    limpar_cache_base_rede_hospital()
    copia = tmp_path / "rede.xlsx"
    shutil.copy2(CAMINHO_XLSX_PADRAO, copia)
    a = carregar_base_rede_hospital(copia)
    lidas = contador_leituras_excel["n"]
    assert carregar_base_rede_hospital(copia) is a
    assert contador_leituras_excel["n"] == lidas
    st = copia.stat()
    os.utime(copia, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    c = carregar_base_rede_hospital(copia)
    assert contador_leituras_excel["n"] > lidas
    assert c is not a
    assert len(c.prestadores) == len(a.prestadores)
