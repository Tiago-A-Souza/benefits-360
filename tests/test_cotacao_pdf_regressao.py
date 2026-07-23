"""Regressão objetiva dos parsers PDF — equivalentes sintéticos (ETAPA 2.5.6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newport_app.cotacao_pdf.apply import aplicar_extracao_confirmada, opcao_candidata_para_rascunho
from newport_app.cotacao_pdf.conferencia import normalizar_opcao
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers import amil, porto, sulamerica
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.cotacao_pdf.validation import pendencias_opcao
from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
)
from newport_app.models.draft import PriceBasisRascunho
from newport_app.siscor_mapper.apply import rascunho_vazio

_FIXTURES = Path(__file__).parent / "fixtures" / "cotacao_pdf"
_ESPERADO_PRIVADO = Path(__file__).resolve().parents[1] / ".private" / "golden" / "cotacao_pdf_homologacao.json"


def _paginas_porto_sintetico() -> list[str]:
    paginas = ["PORTO SEGURO"] * 16
    paginas[1] = (
        "Orçamento:3129336\nRealizado: 30/06/2026 - Validade: 30/07/2026\n"
        "P320 Q COPAR\nPorto Saúde\nR$ 1.500,82\n3 vidas\nApartamento\n"
        "30% de coparticipação\nSubtotal\nR$ 1.500,82\nIOF\nR$ 36,08\n"
        "Valor total mensal para 3 vidas:\nR$ 1.551,90"
    )
    paginas[14] = (
        "tabela geral de prêmios com coparticipação 30%\n"
        "P320 Q COPAR\n227.38\n275.75\n332.64\n380.82\n412.62\n"
        "426.13\n509.02\n547.99\n677.08\n1138.11"
    )
    paginas[15] = (
        "Cotação por faixa etária\nP320 Q COPAR\nR$ 1.500,82\n"
        "19 a 23 anos\n1\n49 a 53 anos\n1\n54 a 58 anos\n1"
    )
    return paginas


def _paginas_sulamerica_sintetico() -> list[str]:
    paginas = ["SUL AMERICA SAUDE"] * 5
    paginas[1] = (
        "Produto Direto SP CAP1\n"
        "R$ 283,94 R$ 354,92 R$ 440,09 R$ 488,51 R$ 522,71 "
        "R$ 606,34 R$ 724,83 R$ 849,51 R$ 1.011,33 R$ 1.703,59\n"
        "Prêmio Saúde: \n + IOF (2,38%): \n = \nR$ 2.215,76\nR$ 52,74\n"
        "Total de Prêmio Saúde: R$ 2.268,50\nValidade da cotação: 14/08/2026"
    )
    return paginas


def _tabela_bradesco_sintetica() -> list[list]:
    linhas = []
    faixas = [
        "Até 18 anos",
        "19 a 23",
        "24 a 28",
        "29 a 33",
        "34 a 38",
        "39 a 43",
        "44 a 48",
        "49 a 53",
        "54 a 58",
        "59 adiante",
    ]
    valores = [35742, 42176, 51032, 61239, 73487, 88184, 87551, 102978, 122543, 214438]
    for rotulo, val in zip(faixas, valores):
        bruto = f"{val // 100},{val % 100:02d}"
        linhas.append([rotulo, None, f"R$ {bruto}", None, None, None, "R$ 22,13", "0", None, "R$ 0,00"])
    linhas.insert(0, ["Perfil 1", None, None])
    linhas.insert(1, ["Plano Saúde", "Nacional III", None, "TN3P"])
    linhas.insert(2, [None, None, "Valores Unitários"])
    linhas.insert(3, ["Faixa Etária", None, "Saúde(R$)", None, None, None, "Dental", "Qtd"])
    return linhas


def test_regressao_porto_sintetico():
    doc = PdfDocumento.from_paginas(_paginas_porto_sintetico())
    opcoes, _, _ = porto.parse(doc, documento_hash="hash-porto")
    assert len(opcoes) == 1
    op = opcoes[0]
    assert len(op.tabela) == 10
    assert op.premio_saude and op.premio_saude.centavos == 150082
    reconciliar_opcao(op)
    assert op.reconciliacao and not op.reconciliacao.ok


def test_regressao_sulamerica_sintetico():
    doc = PdfDocumento.from_paginas(_paginas_sulamerica_sintetico())
    opcoes, _, _ = sulamerica.parse(doc, documento_hash="hash-sul")
    assert len(opcoes) == 1
    op = opcoes[0]
    assert len(op.tabela) == 10
    assert op.premio_saude and op.premio_saude.centavos == 221576
    reconciliar_opcao(op)
    assert op.reconciliacao and op.reconciliacao.ok


def test_regressao_amil_quatro_opcoes_sintetico():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((36, 100), "0 a 18 19 a 23 24 a 28 29 a 33 34 a 38 39 a 43 44 a 48 49 a 53 54 a 58 59+", fontsize=8)
    vals_a = " ".join(f"R$ {100 + i * 10},00" for i in range(10))
    vals_b = " ".join(f"R$ {200 + i * 10},00" for i in range(10))
    page.insert_text((36, 115), f"PlanoA {vals_a}", fontsize=8)
    page.insert_text((36, 130), f"PlanoB {vals_b}", fontsize=8)
    conteudo = doc.tobytes()
    doc.close()
    with PdfDocumento.abrir(conteudo) as pdf:
        pdf.paginas_texto[0] = "AMIL ONE\n" + pdf.paginas_texto[0]
        opcoes, alertas, _ = amil.parse(pdf, documento_hash="hash-amil")
    assert not alertas
    assert len(opcoes) >= 2
    for op in opcoes:
        assert len(op.tabela) == 10


def test_regressao_bradesco_dois_perfis_sintetico():
    from newport_app.cotacao_pdf.parsers.bradesco import _parse_tabela

    tabela = _tabela_bradesco_sintetica()
    nome, linhas, _ = _parse_tabela(tabela, 0)
    assert "Nacional" in nome
    assert len(linhas) == 10


def test_regressao_omint_ocr_pendente():
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "OMINT")
    conteudo = doc.tobytes()
    doc.close()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="t",
        documento_id="d-omint",
        nome_arquivo="omint.pdf",
    )
    assert ext.estado == "ocr_pendente"
    assert ext.documento.template_id == "omint-ocr-v1"


def test_apply_nao_inventa_defaults():
    op = OpcaoCotacaoCandidata(
        id="op-1",
        operadora=novo_campo("Operadora", texto="Porto Seguro", estado="confirmar"),
        plano_nome=novo_campo("Nome do plano", texto="P320 Q", estado="confirmar"),
        regime_copart=novo_campo("Regime de coparticipação", texto="parcial", estado="revisar"),
        tabela=[
            faixa_extraida(
                0,
                valor_centavos=10000,
                quantidade=1,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                pagina=1,
                trecho_valor="x",
                trecho_qtd="1",
                parser_versao="t",
                documento_hash="h",
            )
        ],
    )
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    assert pendencias_opcao(op)
    resultado = opcao_candidata_para_rascunho(
        op,
        extracao_id="ext-1",
        documento_id="doc-1",
        documento_hash="h",
        parser_versao="t",
    )
    assert resultado is None


def test_apply_bloqueia_divergencia():
    op = OpcaoCotacaoCandidata(id="op-2")
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    for campo in (op.operadora, op.plano_nome, op.tipo_fiscal, op.regime_copart):
        assert campo is not None
        if campo.rotulo == "Tipo fiscal":
            campo.texto = "seguradora"
        if campo.rotulo == "Regime de coparticipação":
            campo.texto = "sem"
        campo.confirmado = True
        campo.estado = "confirmar"
    op.tabela = [
        faixa_extraida(
            1,
            valor_centavos=50000,
            quantidade=1,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="x",
            trecho_qtd="1",
            parser_versao="t",
            documento_hash="h",
        )
    ]
    op.tabela[0].valor.confirmado = True
    op.tabela[0].quantidade.confirmado = True
    op.premio_saude = novo_campo("Prêmio saúde", centavos=99999, parser_versao="t", documento_hash="h")
    op.premio_saude.confirmado = True
    reconciliar_opcao(op)
    assert op.reconciliacao and not op.reconciliacao.ok
    assert pendencias_opcao(op)


def test_apply_atualiza_sem_duplicar():
    op = OpcaoCotacaoCandidata(id="op-canonica")
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    for campo in (op.operadora, op.plano_nome, op.tipo_fiscal, op.regime_copart):
        assert campo
        if campo.rotulo == "Tipo fiscal":
            campo.texto = "seguradora"
        if campo.rotulo == "Regime de coparticipação":
            campo.texto = "sem"
        if campo.rotulo == "Operadora":
            campo.texto = "Porto Seguro"
        if campo.rotulo == "Nome do plano":
            campo.texto = "P320"
        campo.confirmado = True
        campo.estado = "confirmar"
    op.tabela = [
        faixa_extraida(
            0,
            valor_centavos=10000,
            quantidade=1,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="x",
            trecho_qtd="1",
            parser_versao="t",
            documento_hash="h",
        )
    ]
    op.tabela[0].valor.confirmado = True
    op.tabela[0].quantidade.confirmado = True
    op.premio_saude = novo_campo("Prêmio saúde", centavos=10000, parser_versao="t", documento_hash="h")
    op.premio_saude.confirmado = True
    reconciliar_opcao(op)

    extracao = ExtracaoCotacaoCandidata(
        id="ext-1",
        estudo_id="demo",
        versao=1,
        documento=DocumentoCotacaoPDF(
            id="doc-1",
            nome_arquivo="x.pdf",
            hash_sha256="h",
            parser_versao="porto@1",
        ),
        estado="extraido",
        opcoes=[op],
        criado_em=datetime.now(timezone.utc),
    )
    rascunho = rascunho_vazio("demo", "Demo")
    rascunho, b1 = aplicar_extracao_confirmada(rascunho, extracao)
    assert not b1
    assert len(rascunho.opcoes_proposta) == 1
    rascunho, b2 = aplicar_extracao_confirmada(rascunho, extracao)
    assert not b2
    assert len(rascunho.opcoes_proposta) == 1
    assert rascunho.opcoes_proposta[0].extracao_opcao_id == "op-canonica"


def test_esperado_versionado_alinhado():
    esperado_path = _FIXTURES / "regressao_esperada.json"
    assert esperado_path.is_file()
    esperado = json.loads(esperado_path.read_text(encoding="utf-8"))
    assert esperado["porto"]["premio_centavos"] == 150082
    assert esperado["porto"]["reconciliacao_ok"] is False
    assert esperado["sulamerica"]["reconciliacao_ok"] is True
    if _ESPERADO_PRIVADO.is_file():
        privado = json.loads(_ESPERADO_PRIVADO.read_text(encoding="utf-8"))
        assert privado["Porto"]["premio_centavos"] == esperado["porto"]["premio_centavos"]


@pytest.mark.private_corpus
def test_regressao_privada_porto():
    path = Path(r"C:\0-Projetos\0-Claude_Cowork\@Newport\Newport-Teste-ATEF\PORTO.pdf")
    if not path.is_file():
        pytest.skip("Corpus privado indisponível")
    ext = parse_cotacao_pdf(path.read_bytes(), estudo_id="h", documento_id="d", nome_arquivo="p.pdf")
    assert ext.opcoes[0].premio_saude.centavos == 150082
    assert len(ext.opcoes[0].tabela) == 10
