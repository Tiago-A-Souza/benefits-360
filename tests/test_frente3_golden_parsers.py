"""Frente 3 — goldens sintéticos por família de parser PDF."""

from __future__ import annotations

import pytest

from newport_app.cotacao_pdf.parsers import amil, bradesco, porto, sulamerica
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from tests.fixtures.cotacao_pdf.build_pdfs import (
    build_amil_bronze_sem_acomodacao,
    build_amil_prata_qc_milhar,
    build_amil_sem_tabela,
    build_bradesco_doc_caso_feliz,
    build_bradesco_doc_sem_tabelas,
    build_porto_27_paginas,
    build_porto_27_serie_p220,
    build_porto_sem_tabela_geral,
    build_porto_sem_validade,
    build_sulamerica_com_copart,
    build_sulamerica_faixa_unica_com_vidas,
    build_sulamerica_sem_copart,
    build_sulamerica_sem_tabela,
)
from tests.fixtures.cotacao_pdf.golden_snapshot import (
    RESSALVA_DEDUCAO_ACOMODACAO,
    assert_extracao_igual_golden,
    carregar_golden,
    serializar_extracao,
    serializar_parse_direto,
)

_AMIL_CASOS = {
    "caso_feliz_prata_qc": (build_amil_prata_qc_milhar, True),
    "bronze_sem_acomodacao": (build_amil_bronze_sem_acomodacao, False),
    "layout_sem_tabela": (build_amil_sem_tabela, False),
}

_PORTO_CASOS = {
    "caso_feliz_p320": (build_porto_27_paginas, True),
    "serie_p220": (build_porto_27_serie_p220, True),
    "sem_validade": (build_porto_sem_validade, True),
    "layout_sem_tabela_geral": (build_porto_sem_tabela_geral, True),
}

_SUL_CASOS = {
    "caso_feliz_sem_copart": (build_sulamerica_sem_copart, False),
    "com_acomodacao_faixa_unica": (build_sulamerica_faixa_unica_com_vidas, False),
    "dois_regimes_copart": (build_sulamerica_com_copart, False),
    "layout_sem_tabela": (build_sulamerica_sem_tabela, False),
}

_BRADESCO_CASOS = {
    "caso_feliz_tabela": build_bradesco_doc_caso_feliz,
    "layout_sem_tabelas": build_bradesco_doc_sem_tabelas,
}


def _parse_pdf(builder, nome: str, *, ressalva: bool = False) -> dict:
    ext = parse_cotacao_pdf(
        builder(),
        estudo_id="golden",
        documento_id="d",
        nome_arquivo=nome,
    )
    return serializar_extracao(ext, incluir_ressalva_deducao=ressalva)


def _parse_bradesco(builder) -> dict:
    doc = builder()
    opcoes, alertas, _ = bradesco.parse(doc, documento_hash="golden-bra")
    return serializar_parse_direto(
        opcoes,
        alertas,
        parser_versao=bradesco.PARSER_VERSAO,
        template_id=bradesco.TEMPLATE_ID,
    )


@pytest.mark.parametrize("caso", sorted(_AMIL_CASOS))
def test_golden_amil(caso: str):
    builder, ressalva = _AMIL_CASOS[caso]
    atual = _parse_pdf(builder, f"amil-{caso}.pdf", ressalva=ressalva)
    esperado = carregar_golden("amil", caso)
    assert_extracao_igual_golden(atual, esperado, familia="amil", caso=caso)


@pytest.mark.parametrize("caso", sorted(_PORTO_CASOS))
def test_golden_porto(caso: str):
    builder, ressalva = _PORTO_CASOS[caso]
    atual = _parse_pdf(builder, f"porto-{caso}.pdf", ressalva=ressalva)
    esperado = carregar_golden("porto", caso)
    assert_extracao_igual_golden(atual, esperado, familia="porto", caso=caso)


@pytest.mark.parametrize("caso", sorted(_SUL_CASOS))
def test_golden_sulamerica(caso: str):
    builder, ressalva = _SUL_CASOS[caso]
    atual = _parse_pdf(builder, f"sul-{caso}.pdf", ressalva=ressalva)
    esperado = carregar_golden("sulamerica", caso)
    assert_extracao_igual_golden(atual, esperado, familia="sulamerica", caso=caso)


@pytest.mark.parametrize("caso", sorted(_BRADESCO_CASOS))
def test_golden_bradesco(caso: str):
    atual = _parse_bradesco(_BRADESCO_CASOS[caso])
    esperado = carregar_golden("bradesco", caso)
    assert_extracao_igual_golden(atual, esperado, familia="bradesco", caso=caso)


def test_golden_amil_ressalva_texto_canonico():
    esperado = carregar_golden("amil", "caso_feliz_prata_qc")
    assert esperado["_ressalva_deducacao_acomodacao"] == RESSALVA_DEDUCAO_ACOMODACAO


def test_golden_amil_mutacao_detecta_regressao(monkeypatch):
    original = amil._valores_linha

    def _mutado(words):
        vals = original(words)
        if vals:
            vals[0] += 1
        return vals

    monkeypatch.setattr(amil, "_valores_linha", _mutado)
    builder, ressalva = _AMIL_CASOS["caso_feliz_prata_qc"]
    atual = _parse_pdf(builder, "amil-mut.pdf", ressalva=ressalva)
    esperado = carregar_golden("amil", "caso_feliz_prata_qc")
    with pytest.raises(AssertionError):
        assert_extracao_igual_golden(atual, esperado, familia="amil", caso="mutacao")


def test_golden_porto_mutacao_detecta_regressao(monkeypatch):
    import newport_app.cotacao_pdf.coords_extract as coords

    original = coords._eh_nome_plano_valido
    monkeypatch.setattr(coords, "_eh_nome_plano_valido", lambda nome: False)
    builder, ressalva = _PORTO_CASOS["caso_feliz_p320"]
    atual = _parse_pdf(builder, "porto-mut.pdf", ressalva=ressalva)
    monkeypatch.setattr(coords, "_eh_nome_plano_valido", original)
    esperado = carregar_golden("porto", "caso_feliz_p320")
    with pytest.raises(AssertionError):
        assert_extracao_igual_golden(atual, esperado, familia="porto", caso="mutacao")


def test_golden_sulamerica_mutacao_detecta_regressao(monkeypatch):
    original = sulamerica._extrair_financeiro

    def _mutado(doc, paginas):
        premio, iof, total, validade = original(doc, paginas)
        return (premio + 1 if premio else premio, iof, total, validade)

    monkeypatch.setattr(sulamerica, "_extrair_financeiro", _mutado)
    builder, _ = _SUL_CASOS["caso_feliz_sem_copart"]
    atual = _parse_pdf(builder, "sul-mut.pdf")
    esperado = carregar_golden("sulamerica", "caso_feliz_sem_copart")
    with pytest.raises(AssertionError):
        assert_extracao_igual_golden(atual, esperado, familia="sulamerica", caso="mutacao")


def test_golden_bradesco_mutacao_detecta_regressao(monkeypatch):
    original = bradesco._parse_tabela

    def _mutado(tabela, indice):
        nome, linhas, subtotal = original(tabela, indice)
        linhas_mut = [
            (faixa, centavos + 1 if centavos else centavos, qtd, rotulo)
            for faixa, centavos, qtd, rotulo in linhas
        ]
        return nome, linhas_mut, subtotal

    monkeypatch.setattr(bradesco, "_parse_tabela", _mutado)
    atual = _parse_bradesco(build_bradesco_doc_caso_feliz)
    esperado = carregar_golden("bradesco", "caso_feliz_tabela")
    with pytest.raises(AssertionError):
        assert_extracao_igual_golden(atual, esperado, familia="bradesco", caso="mutacao")
