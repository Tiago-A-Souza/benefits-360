"""Valor de fatura opcional em seguro novo; obrigatório em renovação."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.importacao_siscor import ImportacaoSiscorService
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_app.siscor_mapper.apply import rascunho_vazio
from tests.fixtures.siscor.xlsx_builder import (
    planilha_12_vidas,
    planilha_12_vidas_valores_zerados,
)


@pytest.fixture
def servico(tmp_path: Path) -> ImportacaoSiscorService:
    estudos = SQLiteStudyRepository(tmp_path / "estudos.db")
    imports = ImportacaoSiscorRepository(tmp_path / "imports.db")
    return ImportacaoSiscorService(estudos, imports, uploads_dir=tmp_path / "uploads")


def test_seguro_novo_valores_zerados_confirmaveis():
    resultado = parse_planilha_siscor(
        planilha_12_vidas_valores_zerados(),
        estudo_id="novo-z",
        documento_id="d",
        formato="novo",
    )
    assert resultado.sucesso
    assert resultado.candidata is not None
    assert resultado.candidata.estatisticas.total_linhas_lidas == 12
    assert resultado.candidata.estatisticas.linhas_com_excecao == 0
    assert all(linha.confirmavel for linha in resultado.candidata.linhas)
    codigos = {a.codigo for linha in resultado.candidata.linhas for a in linha.alertas}
    assert "APP-SIS-003" not in codigos
    assert "APP-SIS-009" not in codigos


def test_renovacao_valores_zerados_preserva_app_sis_003():
    resultado = parse_planilha_siscor(
        planilha_12_vidas_valores_zerados(),
        estudo_id="ren-z",
        documento_id="d",
        formato="renovacao",
    )
    assert resultado.sucesso
    assert resultado.candidata is not None
    assert resultado.candidata.estatisticas.linhas_com_excecao == 12
    assert all(not linha.confirmavel for linha in resultado.candidata.linhas)
    assert all(
        any(a.codigo == "APP-SIS-003" for a in linha.alertas)
        for linha in resultado.candidata.linhas
    )


def test_seguro_novo_com_valores_preenchidos_ok():
    resultado = parse_planilha_siscor(
        planilha_12_vidas(),
        estudo_id="novo-v",
        documento_id="d",
        formato="novo",
    )
    assert resultado.sucesso
    assert resultado.candidata is not None
    assert resultado.candidata.estatisticas.linhas_com_excecao == 0
    assert all(linha.confirmavel for linha in resultado.candidata.linhas)


def test_formato_indefinido_valor_zerado_info_nao_bloqueia():
    resultado = parse_planilha_siscor(
        planilha_12_vidas_valores_zerados(),
        estudo_id="ind",
        documento_id="d",
        formato=None,
    )
    assert resultado.sucesso
    assert resultado.candidata is not None
    assert resultado.candidata.estatisticas.linhas_com_excecao == 0
    assert all(linha.confirmavel for linha in resultado.candidata.linhas)
    infos = [
        a
        for linha in resultado.candidata.linhas
        for a in linha.alertas
        if a.codigo == "APP-SIS-003"
    ]
    assert infos
    assert all(a.severidade == "info" for a in infos)


def test_estudo_seguro_novo_confirma_lote(servico: ImportacaoSiscorService, tmp_path: Path):
    estudos = servico._estudos
    rascunho = rascunho_vazio("est-novo-lote", "Seguro novo IVTEC", formato="novo")
    estudos.salvar_rascunho(rascunho)

    out = servico.importar_planilha(
        "est-novo-lote",
        planilha_12_vidas_valores_zerados(),
        titulo="Seguro novo IVTEC",
    )
    assert out.sucesso
    assert out.resumo is not None
    assert out.resumo.estatisticas.linhas_com_excecao == 0

    conf = servico.confirmar_lote("est-novo-lote", confirmado_por="analista")
    assert conf.confirmadas == 12
    assert conf.vidas_no_rascunho == 12

    depois = estudos.obter_rascunho("est-novo-lote")
    assert depois is not None
    assert depois.formato == "novo"
    assert len([v for v in depois.vidas if v.incluida]) == 12
