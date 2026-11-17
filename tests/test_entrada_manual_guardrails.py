"""Guardrails da entrada manual (itens 1–3, 5) — sem tocar no motor."""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    OpcaoPropostaRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    TabelaFaixaRascunho,
)
from newport_app.models.snapshot import SNAPSHOT_VERSAO
from newport_app.rascunho.conferencia_manual import (
    LIMIAR_AVISO_CENTAVOS,
    LIMIAR_OK_CENTAVOS,
    SeveridadeConferenciaManual,
    conferir_totais_opcao_manual,
    subtotal_faixas_puro_centavos,
)
from newport_app.siscor_importer.constants import COLUNAS_OBRIGATORIAS
from newport_app.siscor_importer.parser import parse_planilha_siscor


def _faixa(i: int, centavos: int, qtd: int, basis: PriceBasisRascunho) -> TabelaFaixaRascunho:
    return TabelaFaixaRascunho(
        faixa=i,
        valor_centavos=centavos,
        quantidade_cotada=qtd,
        price_basis=basis,
        proveniencia=ProvenienciaRascunho(origem="manual", extrator_versao="manual", confirmado=True),
    )


def _comp(centavos: int, basis: PriceBasisRascunho) -> ComponenteFinanceiroRascunho:
    return ComponenteFinanceiroRascunho(
        centavos=centavos,
        price_basis=basis,
        proveniencia=ProvenienciaRascunho(origem="manual", extrator_versao="manual", confirmado=True),
    )


def test_quantidade_null_ainda_bloqueia_app_qtd_001():
    """Item 1: default 0 é da UI; null vindo de outro caminho continua APP-QTD-001."""
    from newport_app.draft_compiler.finance_validation import validar_faixa_tabela
    from newport_app.models.compilation import ErroCompilacao

    fx = TabelaFaixaRascunho(
        faixa=0,
        valor_centavos=10000,
        quantidade_cotada=None,
        price_basis=PriceBasisRascunho.EXCLUI_IOF,
        proveniencia=ProvenienciaRascunho(origem="manual", extrator_versao="manual", confirmado=True),
    )
    erros: list[ErroCompilacao] = []
    ok = validar_faixa_tabela(fx, "seguradora", "/opcoes_proposta/0/tabela/0", erros, exigir_quantidade=True)
    assert ok is False
    assert any(e.codigo == "APP-QTD-001" for e in erros)


def test_quantidade_zero_passa_validacao():
    from newport_app.draft_compiler.finance_validation import validar_faixa_tabela
    from newport_app.models.compilation import ErroCompilacao

    fx = _faixa(0, 10000, 0, PriceBasisRascunho.EXCLUI_IOF)
    erros: list[ErroCompilacao] = []
    ok = validar_faixa_tabela(fx, "seguradora", "/t/0", erros, exigir_quantidade=True)
    assert ok is True
    assert not erros


def test_conferencia_ok_dentro_de_5_centavos():
    # 2 vidas × 100,00 exclui IOF seguradora → com IOF 2,38% = 204,76
    op = OpcaoPropostaRascunho(
        id="op-1",
        operadora="Bradesco",
        plano_nome="Efetivo",
        regime_copart_id="regime-sem",
        tipo_fiscal="seguradora",
        tabela=[_faixa(0, 10000, 2, PriceBasisRascunho.EXCLUI_IOF)],
        total_recorrente=_comp(20476, PriceBasisRascunho.INCLUI_IOF),
    )
    # calc: apply 2.38% on 20000 = 20476
    res = conferir_totais_opcao_manual(op)
    assert res.severidade == SeveridadeConferenciaManual.OK
    assert res.diff_centavos is not None
    assert res.diff_centavos <= LIMIAR_OK_CENTAVOS


def test_conferencia_aviso_entre_6_e_100_centavos():
    op = OpcaoPropostaRascunho(
        id="op-1",
        operadora="Bradesco",
        plano_nome="Efetivo",
        regime_copart_id="regime-sem",
        tipo_fiscal="seguradora",
        tabela=[_faixa(0, 10000, 2, PriceBasisRascunho.EXCLUI_IOF)],
        # 50 centavos a mais que 20476
        total_recorrente=_comp(20526, PriceBasisRascunho.INCLUI_IOF),
    )
    res = conferir_totais_opcao_manual(op)
    assert res.severidade == SeveridadeConferenciaManual.AVISO
    assert res.diff_centavos is not None
    assert LIMIAR_OK_CENTAVOS < res.diff_centavos <= LIMIAR_AVISO_CENTAVOS


def test_conferencia_bloqueio_acima_de_1_real():
    op = OpcaoPropostaRascunho(
        id="op-1",
        operadora="Bradesco",
        plano_nome="Efetivo",
        regime_copart_id="regime-sem",
        tipo_fiscal="seguradora",
        tabela=[_faixa(0, 10000, 2, PriceBasisRascunho.EXCLUI_IOF)],
        total_recorrente=_comp(22000, PriceBasisRascunho.INCLUI_IOF),
    )
    res = conferir_totais_opcao_manual(op)
    assert res.severidade == SeveridadeConferenciaManual.BLOQUEIO
    assert res.diff_centavos is not None
    assert res.diff_centavos > LIMIAR_AVISO_CENTAVOS
    assert "tipo fiscal" in res.mensagem.lower() or "base de preço" in res.mensagem.lower()


def test_nao_consta_no_pdf_aviso_sem_bloqueio():
    op = OpcaoPropostaRascunho(
        id="op-1",
        operadora="Bradesco",
        plano_nome="Efetivo",
        regime_copart_id="regime-sem",
        tipo_fiscal="seguradora",
        tabela=[_faixa(0, 10000, 2, PriceBasisRascunho.EXCLUI_IOF)],
        total_recorrente=_comp(999999, PriceBasisRascunho.INCLUI_IOF),
        totais_impressos_nao_constam=True,
    )
    res = conferir_totais_opcao_manual(op)
    assert res.severidade == SeveridadeConferenciaManual.AVISO
    assert res.totais_nao_constam is True


def test_ivtec_bradesco_sem_centavos_calculado():
    """Totais do piloto IVTEC (faixas SEM CP × qtds) fecham 7.526,99 com IOF."""
    # Faixas Saúde R$ e qtds do PDF SEM CP
    units = [36609, 43199, 52270, 62725, 71506, 73651, 89674, 105474, 125515, 219638]
    qtds = [4, 2, 4, 0, 0, 1, 0, 0, 0, 1]
    tabela = [
        _faixa(i, u, q, PriceBasisRascunho.EXCLUI_IOF) for i, (u, q) in enumerate(zip(units, qtds))
    ]
    op = OpcaoPropostaRascunho(
        id="brad-sem",
        operadora="Bradesco",
        plano_nome="Efetivo IV",
        regime_copart_id="regime-sem",
        tipo_fiscal="seguradora",
        tabela=tabela,
        total_recorrente=_comp(752699, PriceBasisRascunho.INCLUI_IOF),
    )
    assert subtotal_faixas_puro_centavos(op) == 735203
    res = conferir_totais_opcao_manual(op)
    assert res.total_calculado_centavos == 752699
    assert res.severidade == SeveridadeConferenciaManual.OK


def test_app_sis_f05_lista_colunas_faltantes():
    wb = Workbook()
    ws = wb.active
    ws.append(["CLIENTE", "SEGURADO"])
    buf = BytesIO()
    wb.save(buf)
    resultado = parse_planilha_siscor(buf.getvalue(), estudo_id="x", documento_id="d")
    assert not resultado.sucesso
    f05 = next(e for e in resultado.erros_arquivo if e.codigo == "APP-SIS-F05")
    assert "Faltam:" in f05.mensagem
    assert "PARENTESCO" in f05.colunas_faltantes
    assert "DATA DE NASCIMENTO" in f05.colunas_faltantes
    for col in f05.colunas_faltantes:
        assert col in COLUNAS_OBRIGATORIAS
        assert col in f05.mensagem


def test_snapshot_versao_inalterada():
    assert SNAPSHOT_VERSAO == "2.8.0"
