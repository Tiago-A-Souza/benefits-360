"""Frente 1 — faixas ANS × sexo × titular/dependente (etapa 1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.siscor_importer.faixas_cotacao import (
    montar_tabela_faixas_cotacao,
    tabela_para_tsv,
)
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_motor.faixa import faixa_em
from tests.fixtures.siscor.xlsx_builder import (
    planilha_12_vidas,
    planilha_anistia_41_sintetica,
    planilha_sexo_coluna_celulas_vazias,
)
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)
import json


REF = date(2026, 6, 30)


def _parse(conteudo: bytes):
    return parse_planilha_siscor(conteudo, estudo_id="f1", documento_id="doc-f1")


def test_01_anistia_totais_sexo_tit_dep():
    r = _parse(planilha_anistia_41_sintetica())
    assert r.sucesso and r.candidata
    tab = montar_tabela_faixas_cotacao(
        r.candidata.linhas,
        data_referencia=REF,
        disponibilidade=r.candidata.disponibilidade_colunas,
    )
    assert tab.modo_sexo == "completo"
    assert tab.total_vidas == 41
    assert tab.total_titulares == 27
    assert tab.total_dependentes == 14
    assert tab.total_feminino == 29
    assert tab.total_masculino == 12
    assert len(tab.linhas) == 10


def test_02_soma_celulas_igual_vidas():
    r = _parse(planilha_anistia_41_sintetica())
    tab = montar_tabela_faixas_cotacao(
        r.candidata.linhas,
        data_referencia=REF,
        disponibilidade=r.candidata.disponibilidade_colunas,
    )
    soma = 0
    for ln in tab.linhas:
        soma += (ln.tit_m or 0) + (ln.tit_f or 0) + (ln.dep_m or 0) + (ln.dep_f or 0)
        assert (ln.tit_m or 0) + (ln.tit_f or 0) + (ln.dep_m or 0) + (ln.dep_f or 0) == ln.total
    assert soma == tab.total_vidas == 41
    assert sum(ln.total for ln in tab.linhas) == 41


def test_03_totais_bater_com_estatisticas_etapa1():
    r = _parse(planilha_anistia_41_sintetica())
    c = r.candidata
    tab = montar_tabela_faixas_cotacao(
        c.linhas,
        data_referencia=REF,
        disponibilidade=c.disponibilidade_colunas,
    )
    assert tab.total_titulares == c.estatisticas.qtd_titulares
    assert tab.total_dependentes == c.estatisticas.qtd_dependentes
    assert tab.total_titulares == sum(
        (ln.tit_m or 0) + (ln.tit_f or 0) for ln in tab.linhas
    )
    assert tab.total_dependentes == sum(
        (ln.dep_m or 0) + (ln.dep_f or 0) for ln in tab.linhas
    )


def test_04_faixas_coincidem_com_motor():
    r = _parse(planilha_anistia_41_sintetica())
    c = r.candidata
    por_faixa: dict[int, int] = {i: 0 for i in range(10)}
    for linha in c.linhas:
        if linha.excluida or not linha.nascimento:
            continue
        nasc = date.fromisoformat(linha.nascimento)
        _, fx = faixa_em(nasc, REF)
        por_faixa[fx] += 1
    tab = montar_tabela_faixas_cotacao(
        c.linhas,
        data_referencia=REF,
        disponibilidade=c.disponibilidade_colunas,
    )
    for ln in tab.linhas:
        assert ln.total == por_faixa[ln.faixa]


def test_05_formato_reduzido_sem_sexo():
    r = _parse(planilha_12_vidas())
    tab = montar_tabela_faixas_cotacao(
        r.candidata.linhas,
        data_referencia=REF,
        disponibilidade=r.candidata.disponibilidade_colunas,
    )
    assert tab.modo_sexo == "sem_sexo"
    assert tab.aviso_sexo
    assert "não traz a coluna SEXO" in tab.aviso_sexo
    assert tab.total_feminino is None
    assert tab.total_masculino is None
    for ln in tab.linhas:
        assert ln.tit_m is None
        assert ln.tit_f is None
        assert ln.dep_m is None
        assert ln.dep_f is None
        assert ln.titulares is not None
        assert ln.dependentes is not None
    tsv = tabela_para_tsv(tab)
    assert "Tit. M" not in tsv
    assert "Titulares" in tsv


def test_06_sexo_parcial_coluna_nao_informado():
    r = _parse(planilha_sexo_coluna_celulas_vazias())
    tab = montar_tabela_faixas_cotacao(
        r.candidata.linhas,
        data_referencia=REF,
        disponibilidade=r.candidata.disponibilidade_colunas,
    )
    assert tab.modo_sexo == "parcial"
    assert tab.total_nao_informado == 2
    assert tab.aviso_sexo
    assert any((ln.nao_informado or 0) > 0 for ln in tab.linhas)
    # Ausência não some nas colunas M/F como se fosse zero de categoria — NI separado
    assert sum((ln.tit_m or 0) + (ln.tit_f or 0) + (ln.dep_m or 0) + (ln.dep_f or 0) for ln in tab.linhas) == 2
    assert sum(ln.total for ln in tab.linhas) == 4


def test_07_gabarito_anistia_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"])
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_08_suite_importador_estavel():
    from newport_app.models.siscor_import import IMPORTADOR_SISCOR_VERSAO

    assert IMPORTADOR_SISCOR_VERSAO.startswith("siscor@")


def test_09_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    d1 = hash_snapshot_canonico(snap.payload, versao=snap.snapshot_versao)
    d2 = hash_snapshot_canonico(snap.payload, versao=snap.snapshot_versao)
    assert d1 == d2
    assert len(d1) == 64
    # Estudo demo sem reprocessamento
    demo = rascunho_demo_12_vidas()
    assert all(v.sexo is None for v in demo.vidas)
    assert compile(demo, policy_registry=default_registry).compilavel
