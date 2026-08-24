"""Validade da cotação propaga para todos os planos selecionados."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from newport_app.cotacao_pdf.conferencia import normalizar_extracao, normalizar_opcao
from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
)
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.services.extracao_cotacao import ExtracaoCotacaoService


def test_atualizar_validade_propaga_para_planos_selecionados(tmp_path: Path):
    extracao = ExtracaoCotacaoCandidata(
        id="ext-val",
        estudo_id="est-1",
        versao=1,
        documento=DocumentoCotacaoPDF(id="doc-1", nome_arquivo="t.pdf", hash_sha256="h"),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=[],
    )
    normalizar_extracao(extracao)

    op_a = OpcaoCotacaoCandidata(id="op-a", selecionada_para_comparativo=True)
    op_b = OpcaoCotacaoCandidata(id="op-b", selecionada_para_comparativo=True)
    op_fora = OpcaoCotacaoCandidata(id="op-fora", selecionada_para_comparativo=False)
    for op in (op_a, op_b, op_fora):
        normalizar_opcao(op, parser_versao="t", documento_hash="h")
        op.plano_nome.texto = op.id
        op.operadora.texto = "Porto"
        op.tipo_fiscal.texto = "seguradora"
        op.regime_copart.texto = "sem"
        op.validade_oficial.data = None
    extracao.opcoes.extend([op_a, op_b, op_fora])

    repo = ExtracaoCotacaoRepository(tmp_path / "ext.db")
    repo.salvar(extracao)

    class _EstudosVazio:
        pass

    svc = ExtracaoCotacaoService(_EstudosVazio(), repo, uploads_dir=tmp_path)  # type: ignore[arg-type]

    alvo = date(2026, 7, 2)
    svc.atualizar_campo(
        "ext-val",
        op_a.validade_oficial.id,
        data=alvo,
        confirmado=True,
    )

    gravada = repo.obter_por_id("ext-val")
    assert gravada is not None
    assert gravada.validade_oficial is not None
    assert gravada.validade_oficial.data == alvo
    assert gravada.validade_oficial.confirmado is True

    por_id = {op.id: op for op in gravada.opcoes}
    assert por_id["op-a"].validade_oficial.data == alvo
    assert por_id["op-b"].validade_oficial.data == alvo
    assert por_id["op-a"].validade_oficial.confirmado is True
    assert por_id["op-b"].validade_oficial.confirmado is True
    assert por_id["op-fora"].validade_oficial.data is None
