"""Confirmação implícita ao selecionar planos para o comparativo."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.cotacao_pdf.conferencia import normalizar_opcao
from newport_app.cotacao_pdf.confirmacao import confirmar_opcao_implicita
from newport_app.cotacao_pdf.parsers.base import faixa_extraida
from newport_app.models.cotacao_pdf import OpcaoCotacaoCandidata
from newport_app.models.draft import PriceBasisRascunho


def test_selecionar_plano_confirma_campos_extraidos():
    op = OpcaoCotacaoCandidata(id="op-sel")
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    for campo in (op.operadora, op.plano_nome, op.tipo_fiscal, op.regime_copart):
        assert campo is not None
        if campo.rotulo == "Tipo fiscal":
            campo.texto = "seguradora"
        if campo.rotulo == "Regime de coparticipação":
            campo.texto = "sem"
        if campo.rotulo == "Nome do plano":
            campo.texto = "P320 Q"
        if campo.rotulo == "Operadora":
            campo.texto = "Porto Seguro"
        assert not campo.confirmado
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
    assert not op.tabela[0].valor.confirmado

    n = confirmar_opcao_implicita(op, confirmado_por="selecao")
    assert n > 0
    assert op.plano_nome.confirmado
    assert op.tabela[0].valor.confirmado
    assert op.plano_nome.confirmado_por == "selecao"


def test_confirmar_extracao_propaga_validade_documento_para_opcao():
    from datetime import date, datetime, timezone

    from newport_app.cotacao_pdf.conferencia import normalizar_extracao, normalizar_opcao
    from newport_app.cotacao_pdf.confirmacao import (
        _propagar_validade_documento,
        confirmar_extracao_selecionadas,
    )
    from newport_app.models.cotacao_pdf import (
        DocumentoCotacaoPDF,
        ExtracaoCotacaoCandidata,
        OpcaoCotacaoCandidata,
    )

    extracao = ExtracaoCotacaoCandidata(
        id="ext-v",
        estudo_id="est-1",
        versao=1,
        documento=DocumentoCotacaoPDF(id="doc-1", nome_arquivo="t.pdf", hash_sha256="h"),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=[],
    )
    normalizar_extracao(extracao)

    op_com = OpcaoCotacaoCandidata(id="op-com", selecionada_para_comparativo=True)
    op_sem = OpcaoCotacaoCandidata(id="op-sem", selecionada_para_comparativo=True)
    for op in (op_com, op_sem):
        normalizar_opcao(op, parser_versao="t", documento_hash="h")
        op.plano_nome.texto = op.id
        op.operadora.texto = "Porto"
        op.tipo_fiscal.texto = "seguradora"
        op.regime_copart.texto = "sem"
    op_com.validade_oficial.data = date(2026, 8, 6)
    op_sem.validade_oficial.data = None
    extracao.opcoes.extend([op_com, op_sem])

    _propagar_validade_documento(extracao, op_sem)
    assert op_sem.validade_oficial.data == date(2026, 8, 6)

    confirmar_extracao_selecionadas(extracao, confirmado_por="teste")
    assert op_sem.validade_oficial.confirmado
