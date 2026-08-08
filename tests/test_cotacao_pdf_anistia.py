"""Regressão privada — corpus Anistia Internacional (fora do Git)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from newport_app.config.paths import diretorio_corpus_anistia
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from tests.fixtures.cotacao_pdf.build_pdfs import (
    build_porto_27_paginas,
    build_sulamerica_com_copart,
    build_sulamerica_sem_copart,
)

_CORPUS = diretorio_corpus_anistia()


def _resolver(*nomes: str) -> Path | None:
    if not _CORPUS.is_dir():
        return None
    for nome in nomes:
        hits = list(_CORPUS.rglob(nome))
        if hits:
            return hits[0]
    return None


def _relatorio(ext, arquivo: str) -> dict:
    linhas = []
    for op in ext.opcoes:
        linhas.append(
            {
                "plano": op.plano_nome.texto,
                "regime": op.regime_copart.texto,
                "faixas": len(op.tabela),
                "premio": op.premio_saude.centavos if op.premio_saude else None,
                "iof": op.iof.centavos if op.iof else None,
                "total": op.total_recorrente.centavos if op.total_recorrente else None,
                "reconciliacao_ok": op.reconciliacao.ok if op.reconciliacao else None,
            }
        )
    return {
        "arquivo": arquivo,
        "estado": ext.estado,
        "opcoes": len(ext.opcoes),
        "alertas": [{"codigo": a.codigo, "mensagem": a.mensagem} for a in ext.alertas],
        "campos_confirmados": sum(1 for c in ext.campos_extraidos if c.confirmado),
        "detalhes": linhas,
    }


def test_sintetico_sulamerica_sem_copart():
    ext = parse_cotacao_pdf(
        build_sulamerica_sem_copart(),
        estudo_id="t",
        documento_id="sul-sem",
        nome_arquivo="sul-sem.pdf",
    )
    assert ext.opcoes
    assert all(op.regime_copart.texto == "sem" for op in ext.opcoes)
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert not any(c.confirmado for c in ext.campos_extraidos)


def test_sintetico_sulamerica_com_copart_dois_regimes():
    ext = parse_cotacao_pdf(
        build_sulamerica_com_copart(),
        estudo_id="t",
        documento_id="sul-com",
        nome_arquivo="sul-com.pdf",
    )
    regimes = {op.regime_copart.texto for op in ext.opcoes}
    assert "sem" in regimes
    assert "percentual" in regimes
    assert all(len(op.tabela) == 10 for op in ext.opcoes)


def test_sintetico_porto_27_duas_tabelas():
    ext = parse_cotacao_pdf(
        build_porto_27_paginas(),
        estudo_id="t",
        documento_id="porto27",
        nome_arquivo="porto27.pdf",
    )
    assert len(ext.opcoes) >= 2
    regimes = {op.regime_copart.texto for op in ext.opcoes}
    assert "percentual" in regimes
    # Plano com COPAR no nome prevalece sobre cabeçalho "sem coparticipação" do sintético.
    for op in ext.opcoes:
        if "COPAR" in (op.plano_nome.texto or "").upper():
            assert op.regime_copart.texto == "percentual"
    assert all(len(op.tabela) == 10 for op in ext.opcoes)


@pytest.mark.private_corpus
def test_anistia_sulamerica_com_ajustes():
    path = _resolver("SULAMÉRICA COM AJUSTES.pdf", "SULAMERICA COM AJUSTES.pdf")
    if path is None:
        pytest.skip("Corpus Anistia indisponível")
    ext = parse_cotacao_pdf(path.read_bytes(), estudo_id="anistia", documento_id="sul-aj", nome_arquivo=path.name)
    assert ext.opcoes
    regimes = {op.regime_copart.texto for op in ext.opcoes}
    assert "sem" in regimes
    assert "percentual" in regimes
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert not any(c.confirmado for c in ext.campos_extraidos)


@pytest.mark.private_corpus
def test_anistia_sulamerica_sem_copart():
    path = _resolver("SULAMÉRICA SEM CP.pdf", "SULAMERICA SEM CP.pdf")
    if path is None:
        pytest.skip("Corpus Anistia indisponível")
    ext = parse_cotacao_pdf(path.read_bytes(), estudo_id="anistia", documento_id="sul-sc", nome_arquivo=path.name)
    assert ext.opcoes
    assert all(op.regime_copart.texto == "sem" for op in ext.opcoes)
    assert all(len(op.tabela) == 10 for op in ext.opcoes)


@pytest.mark.private_corpus
def test_anistia_porto_27():
    path = _resolver("PORTO.pdf")
    if path is None:
        pytest.skip("Corpus Anistia indisponível")
    ext = parse_cotacao_pdf(path.read_bytes(), estudo_id="anistia", documento_id="porto", nome_arquivo=path.name)
    assert ext.opcoes
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert not any(c.confirmado for c in ext.campos_extraidos)


@pytest.mark.private_corpus
def test_registrar_relatorio_anistia(tmp_path: Path):
    """Gera matriz de reconciliação privada quando corpus disponível."""
    arquivos = {
        "sul_com_ajustes": _resolver("SULAMÉRICA COM AJUSTES.pdf", "SULAMERICA COM AJUSTES.pdf"),
        "sul_sem_copart": _resolver("SULAMÉRICA SEM CP.pdf", "SULAMERICA SEM CP.pdf"),
        "porto": _resolver("PORTO.pdf"),
    }
    if not any(p is not None for p in arquivos.values()):
        pytest.skip("Corpus Anistia indisponível")
    matriz = {}
    for chave, path in arquivos.items():
        if path is None:
            matriz[chave] = {"erro": "arquivo_indisponivel"}
            continue
        ext = parse_cotacao_pdf(
            path.read_bytes(),
            estudo_id="anistia",
            documento_id=chave,
            nome_arquivo=path.name,
        )
        matriz[chave] = _relatorio(ext, path.name)
    dest = Path(os.environ.get("NEWPORT_GOLDEN_DIR", ".private/golden")) / "anistia_cotacao_pdf.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(matriz, indent=2, ensure_ascii=False), encoding="utf-8")
    assert all(
        matriz[k].get("opcoes", 0) >= 1
        for k in matriz
        if "erro" not in matriz[k]
    )
