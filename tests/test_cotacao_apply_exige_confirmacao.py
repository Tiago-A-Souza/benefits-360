"""Apply exige confirmação humana — via seleção consciente do plano."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.cotacao_pdf.apply import opcao_candidata_para_rascunho
from newport_app.cotacao_pdf.confirmacao import confirmar_extracao_selecionadas
from newport_app.cotacao_pdf.conferencia import normalizar_opcao
from newport_app.cotacao_pdf.parsers.base import faixa_extraida
from newport_app.cotacao_pdf.validation import pendencias_opcao
from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
)
from newport_app.models.draft import PriceBasisRascunho


def _opcao_porto_preenchida(*, selecionada: bool = False) -> OpcaoCotacaoCandidata:
    op = OpcaoCotacaoCandidata(
        id="op-conf",
        selecionada_para_comparativo=selecionada,
    )
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    for campo in (op.operadora, op.plano_nome, op.tipo_fiscal, op.regime_copart):
        assert campo is not None
        if campo.rotulo == "Operadora":
            campo.texto = "Porto Seguro"
        if campo.rotulo == "Nome do plano":
            campo.texto = "BRONZE BRASIL I Q"
        if campo.rotulo == "Tipo fiscal":
            campo.texto = "seguradora"
        if campo.rotulo == "Regime de coparticipação":
            campo.texto = "sem"
        assert not campo.confirmado
    op.tabela = [
        faixa_extraida(
            i,
            valor_centavos=10000 + i * 100,
            quantidade=0,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="x",
            trecho_qtd="0",
            parser_versao="t",
            documento_hash="h",
        )
        for i in range(10)
    ]
    for fx in op.tabela:
        assert not fx.valor.confirmado
    return op


def test_apply_sem_selecao_nao_confirma_proveniencia():
    """Valores extraídos só entram no rascunho após confirmação humana (seleção consciente)."""
    op = _opcao_porto_preenchida(selecionada=False)
    assert not pendencias_opcao(op)

    resultado = opcao_candidata_para_rascunho(
        op,
        extracao_id="ext-1",
        documento_id="doc-1",
        documento_hash="h",
        parser_versao="t",
    )
    assert resultado is None


def test_apply_apos_selecao_confirma_e_monta_proposta():
    op = _opcao_porto_preenchida(selecionada=True)
    extracao = ExtracaoCotacaoCandidata(
        id="ext-1",
        estudo_id="est-1",
        versao=1,
        documento=DocumentoCotacaoPDF(id="doc-1", nome_arquivo="t.pdf", hash_sha256="h"),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=[op],
    )
    confirmar_extracao_selecionadas(extracao, confirmado_por="selecao")

    assert op.regime_copart.confirmado
    assert all(fx.valor.confirmado for fx in op.tabela)

    resultado = opcao_candidata_para_rascunho(
        op,
        extracao_id="ext-1",
        documento_id="doc-1",
        documento_hash="h",
        parser_versao="t",
    )
    assert resultado is not None
    assert resultado.plano_nome == "BRONZE BRASIL I Q"
    assert len(resultado.tabela) == 10
    assert all(fx.proveniencia.confirmado for fx in resultado.tabela)
    assert resultado.premio_saude is None or resultado.premio_saude.proveniencia.confirmado
