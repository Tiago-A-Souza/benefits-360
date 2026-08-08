"""Testes HOTFIX 3.0.3 — extração Porto, referência SISCOR e fluxo de revisão."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from newport_app.config.paths import diretorio_corpus_cotacoes
from newport_app.cotacao_pdf.coords_extract import (
    _nome_coluna_plano,
    classificar_regime_plano_porto,
)
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.models.draft import RascunhoEstudo
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.pendencias import pendencias_compilacao
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual
from newport_app.seed.ficticio import rascunho_demo_12_vidas


_FIXTURE_HASHES = Path(__file__).resolve().parent / "fixtures" / "cotacao_pdf" / "corpus_aceite_hashes.json"
_RE_PRECO_NO_NOME = re.compile(r"\d+[.,]\d{2}")


def _pdf_porto_privado() -> bytes:
    esperado = json.loads(_FIXTURE_HASHES.read_text(encoding="utf-8"))["porto_demonstrativo_27"]
    corpus = diretorio_corpus_cotacoes()
    if not corpus.is_dir():
        pytest.skip("Corpus privado indisponível")
    for pdf in corpus.rglob("*.pdf"):
        conteudo = pdf.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() == esperado:
            return conteudo
    pytest.skip("PDF Porto privado não encontrado")


def _extrair_porto():
    return parse_cotacao_pdf(
        _pdf_porto_privado(),
        estudo_id="hotfix-303",
        documento_id="doc-porto",
        nome_arquivo="sanitizado.pdf",
    )


def test_nome_plano_por_coluna_sem_preco():
    words = [
        (32.0, 160.0, 60.0, 170.0, "OURO"),
        (62.0, 160.0, 80.0, 170.0, "RIO"),
        (85.0, 160.0, 100.0, 170.0, "PRO"),
        (105.0, 160.0, 125.0, 170.0, "COPAR"),
        (135.0, 160.0, 145.0, 170.0, "Q"),
        (150.0, 160.0, 160.0, 170.0, "30"),
        (180.0, 160.0, 210.0, 170.0, "193.97"),
        (220.0, 160.0, 250.0, 170.0, "235.23"),
    ]
    x_limite = 175.0
    nome = _nome_coluna_plano(words, x_limite)
    assert nome == "OURO RIO PRO COPAR Q 30"
    assert "193.97" not in nome
    assert "235.23" not in nome


def test_classifica_copar_30_pelo_nome():
    regime, pct, rotulo = classificar_regime_plano_porto(
        "BRONZE RIO PRO COPAR Q 30",
        "Tabela Geral de Prêmios sem coparticipação",
    )
    assert regime == "parcial"
    assert pct == 30
    assert "30%" in rotulo


def test_nao_usa_sem_copart_como_fallback_ambiguo():
    regime, pct, rotulo = classificar_regime_plano_porto(
        "PLANO DESCONHECIDO XYZ",
        "Tabela Geral de Prêmios — layout incomum",
    )
    assert regime == "a_confirmar"
    assert pct is None
    assert rotulo == "A confirmar"


@pytest.mark.private_corpus
def test_porto_corpus_34_opcoes_nomes_limpos_copar_30():
    ext = _extrair_porto()
    assert len(ext.opcoes) == 34
    assert all(len(op.tabela) == 10 for op in ext.opcoes)
    assert not any(_RE_PRECO_NO_NOME.search(op.plano_nome.texto or "") for op in ext.opcoes)

    sem = [op for op in ext.opcoes if op.regime_copart and op.regime_copart.texto == "sem"]
    parcial = [
        op
        for op in ext.opcoes
        if op.regime_copart
        and op.regime_copart.texto == "parcial"
        and op.copart_percentual
        and op.copart_percentual.inteiro == 30
    ]
    assert len(sem) == 17
    assert len(parcial) == 17
    assert all(op.tipo_fiscal and op.tipo_fiscal.texto == "seguradora" for op in ext.opcoes)
    assert any((op.plano_nome.texto or "").upper().startswith("P220") for op in ext.opcoes)


@pytest.mark.private_corpus
def test_porto_reconciliacao_sem_total_nao_bloqueia():
    ext = _extrair_porto()
    op = ext.opcoes[0]
    for fx in op.tabela:
        fx.quantidade.inteiro = 2
    reconciliar_opcao(op)
    assert op.reconciliacao is not None
    assert op.reconciliacao.status == "nao_conferivel"
    assert op.reconciliacao.ok is True
    assert "não possui total específico" in (op.reconciliacao.mensagem or "")


def test_resumo_plano_atual_com_referencia_centavos():
    rascunho = rascunho_demo_12_vidas()
    resumo = montar_resumo_plano_atual(rascunho)
    assert resumo.planos
    item = resumo.planos[0]
    assert item.quantidade_beneficiarios > 0
    assert item.referencia_comparativo in ("vigente", "reajustada")
    assert item.reajuste_bps is not None
    assert item.reajuste_percentual_exibicao is not None


def test_ausencia_propostas_nao_bloqueia_etapa_2():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta = []
    rascunho.cenarios = []
    itens = pendencias_compilacao(rascunho)
    etapa2 = [p for p in itens if p.etapa == 2 and p.tipo == "bloqueio"]
    assert not any(p.codigo == "APP-ET3-001" for p in etapa2)


def test_estudo_real_resumo_plano_atual():
    origem = Path(".data/newport_app.db")
    if not origem.is_file():
        pytest.skip("Banco real indisponível")
    repo = SQLiteStudyRepository(origem)
    rascunho = repo.obter_rascunho("est-6ec6d7945a")
    if rascunho is None:
        pytest.skip("Estudo real não encontrado")
    resumo = montar_resumo_plano_atual(rascunho)
    assert len(resumo.planos) == 2
    assert all(p.quantidade_beneficiarios > 0 for p in resumo.planos)
    assert resumo.planos[0].valor_mensal_vigente_centavos is not None
