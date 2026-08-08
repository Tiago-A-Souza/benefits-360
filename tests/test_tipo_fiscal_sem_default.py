"""tipo_fiscal ausente não recebe default silencioso; IOF só após declaração."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.cotacao_pdf.apply import aplicar_extracao_confirmada, opcao_candidata_para_rascunho
from newport_app.cotacao_pdf.conferencia import normalizar_opcao
from newport_app.cotacao_pdf.confirmacao import confirmar_opcao_implicita
from newport_app.cotacao_pdf.estimativa import estimar_opcao_candidata
from newport_app.cotacao_pdf.parsers.base import faixa_extraida
from newport_app.cotacao_pdf.validation import pendencias_opcao
from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
)
from newport_app.models.draft import PriceBasisRascunho
from newport_app.siscor_mapper.apply import rascunho_vazio

# Base IVTEC 12 vidas — distribuição que totaliza os valores do estudo entregue.
_QTD_IVTEC = {0: 4, 1: 2, 2: 4, 3: 0, 4: 0, 5: 1, 6: 0, 7: 0, 8: 0, 9: 1}

_BRONZE = [17938, 24360, 28595, 28595, 28595, 31941, 44111, 52669, 75737, 107396]
_PRATA = [28290, 33100, 40382, 48458, 50881, 55969, 69962, 76958, 96198, 168347]


def _opcao_amil(valores: list[int], *, com_tipo_fiscal: str | None = None) -> OpcaoCotacaoCandidata:
    op = OpcaoCotacaoCandidata(id="op-amil", selecionada_para_comparativo=True)
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    assert op.operadora and op.plano_nome and op.tipo_fiscal and op.regime_copart
    op.operadora.texto = "Amil"
    op.plano_nome.texto = "Bronze SP + TP"
    op.regime_copart.texto = "parcial"
    if com_tipo_fiscal is not None:
        op.tipo_fiscal.texto = com_tipo_fiscal
    op.tabela = [
        faixa_extraida(
            i,
            valor_centavos=v,
            quantidade=_QTD_IVTEC.get(i, 0),
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="x",
            trecho_qtd=str(_QTD_IVTEC.get(i, 0)),
            parser_versao="t",
            documento_hash="h",
        )
        for i, v in enumerate(valores)
    ]
    return op


def test_confirmacao_nao_aplica_default_tipo_fiscal():
    op = _opcao_amil(_BRONZE, com_tipo_fiscal=None)
    assert op.tipo_fiscal is not None
    assert not op.tipo_fiscal.texto

    confirmar_opcao_implicita(op, confirmado_por="teste")

    assert not op.tipo_fiscal.texto
    assert any("Tipo fiscal" in m for m in pendencias_opcao(op))


def test_confirmacao_nao_aplica_default_regime_copart():
    op = _opcao_amil(_BRONZE, com_tipo_fiscal="operadora")
    assert op.regime_copart is not None
    op.regime_copart.texto = None

    confirmar_opcao_implicita(op, confirmado_por="teste")

    assert not op.regime_copart.texto
    assert any("Regime de coparticipação" in m for m in pendencias_opcao(op))


def test_aplicar_sem_tipo_fiscal_e_recusado():
    op = _opcao_amil(_BRONZE, com_tipo_fiscal=None)
    confirmar_opcao_implicita(op, confirmado_por="selecao")

    rascunho = rascunho_vazio("est-tf", "IVTEC")
    extracao = ExtracaoCotacaoCandidata(
        id="ext-1",
        estudo_id="est-tf",
        versao=1,
        documento=DocumentoCotacaoPDF(id="doc-1", nome_arquivo="amil.pdf", hash_sha256="h"),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=[op],
    )
    _, bloqueios = aplicar_extracao_confirmada(rascunho, extracao)

    assert rascunho.opcoes_proposta == []
    assert bloqueios
    assert any("Tipo fiscal" in m for b in bloqueios for m in b["motivos"])
    assert opcao_candidata_para_rascunho(
        op,
        extracao_id="ext-1",
        documento_id="doc-1",
        documento_hash="h",
        parser_versao="t",
    ) is None


def test_amil_operadora_sem_iof_totais_ivtec():
    qtd_int = dict(_QTD_IVTEC)

    bronze = _opcao_amil(_BRONZE, com_tipo_fiscal="operadora")
    prata = _opcao_amil(_PRATA, com_tipo_fiscal="operadora")
    prata.plano_nome.texto = "Prata TP"

    assert estimar_opcao_candidata(bronze, qtd_int) == 374_189
    assert estimar_opcao_candidata(prata, qtd_int) == 565_204


def test_seguradora_aplica_iof():
    qtd_int = dict(_QTD_IVTEC)
    bronze = _opcao_amil(_BRONZE, com_tipo_fiscal="seguradora")
    total = estimar_opcao_candidata(bronze, qtd_int)
    assert total == 383_097  # 374189 * 1.0238 com arredondamento por vida


def test_tipo_fiscal_ja_extraido_permanece():
    op = _opcao_amil(_BRONZE, com_tipo_fiscal="seguradora")
    op.tipo_fiscal.evidencia.trecho = "Porto Seguro — seguradora"
    confirmar_opcao_implicita(op, confirmado_por="selecao")
    assert op.tipo_fiscal.texto == "seguradora"
    assert op.tipo_fiscal.confirmado


def test_estimativa_sem_tipo_fiscal_retorna_none():
    op = _opcao_amil(_BRONZE, com_tipo_fiscal=None)
    assert estimar_opcao_candidata(op, dict(_QTD_IVTEC)) is None
