"""Alertas de acomodação divergente + dedupe de planos idênticos entre PDFs."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.cotacao_pdf.apply import aplicar_extracao_confirmada
from newport_app.cotacao_pdf.conferencia import normalizar_opcao
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.parsers import amil
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.draft_compiler import compile
from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
)
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    CenarioRascunho,
    EscolhasEstudo,
    PriceBasisRascunho,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    VidaRascunho,
)
from newport_app.seed.ficticio import _faixa_atual
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.rascunho.acomodacao import (
    coletar_divergencias_acomodacao,
    pendencias_divergencia_acomodacao,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.pendencias import pendencias_compilacao
from newport_app.services.snapshot import SnapshotService
from newport_app.siscor_mapper.apply import rascunho_vazio
from newport_motor.engine import calcular

_LUNVOX = Path(r"C:\Users\tiago\Downloads\LUNVOX-20260809T012504Z-1-001\LUNVOX")

# Contagens e unitários da pág. 4 dos PDFs Amil Lunvox (QC 31 vidas + QP 16).
_QTD_QC = [5, 4, 10, 4, 6, 2, 0, 0, 0, 0]
_QTD_QP = [1, 0, 5, 4, 2, 2, 1, 0, 1, 0]
_PRATA_QC = [20596, 24097, 29398, 35277, 37041, 40746, 50932, 56026, 70032, 122556]
_PRATA_QP = [22862, 26749, 32634, 39161, 41119, 45231, 56539, 62193, 77742, 136048]
_OURO_QP = [28617, 33482, 40849, 49018, 51469, 56617, 70771, 77848, 97310, 170293]
_PLAT_QP = [39473, 46183, 56344, 67613, 70994, 78093, 97616, 107379, 134223, 234891]
_S750_QP = [36751, 42998, 52458, 62950, 66097, 72707, 90884, 99973, 124966, 218691]


def _pasta_cotacoes() -> Path | None:
    if not _LUNVOX.is_dir():
        return None
    return next(
        (p for p in _LUNVOX.rglob("*") if p.is_dir() and "COTA" in p.name.upper()),
        None,
    )


def _opcao_pronta(
    *,
    opcao_id: str,
    nome: str,
    valores: list[int],
    acomodacao: str | None,
    doc_hash: str = "h",
) -> OpcaoCotacaoCandidata:
    op = OpcaoCotacaoCandidata(id=opcao_id, selecionada_para_comparativo=True)
    normalizar_opcao(op, parser_versao="t", documento_hash=doc_hash)
    assert op.operadora and op.plano_nome and op.tipo_fiscal and op.regime_copart
    op.operadora.texto = "Amil"
    op.plano_nome.texto = nome
    op.tipo_fiscal.texto = "operadora"
    op.regime_copart.texto = "parcial"
    for campo in (op.operadora, op.plano_nome, op.tipo_fiscal, op.regime_copart):
        campo.confirmado = True
        campo.estado = "confirmar"
    if acomodacao:
        op.acomodacao = novo_campo(
            "Acomodação",
            texto=acomodacao,
            estado="confirmar",
            parser_versao="t",
            documento_hash=doc_hash,
        )
        op.acomodacao.confirmado = True
    op.tabela = [
        faixa_extraida(
            i,
            valor_centavos=v,
            quantidade=0,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="x",
            trecho_qtd="0",
            parser_versao="t",
            documento_hash=doc_hash,
        )
        for i, v in enumerate(valores)
    ]
    for fx in op.tabela:
        fx.valor.confirmado = True
        fx.quantidade.confirmado = True
    reconciliar_opcao(op)
    return op


def _extracao(doc_id: str, ext_id: str, opcoes: list[OpcaoCotacaoCandidata]) -> ExtracaoCotacaoCandidata:
    return ExtracaoCotacaoCandidata(
        id=ext_id,
        estudo_id="lunvox",
        versao=1,
        documento=DocumentoCotacaoPDF(
            id=doc_id,
            nome_arquivo=f"{doc_id}.pdf",
            hash_sha256=doc_id,
            parser_versao="amil@1.2.0",
            operadora_detectada="Amil",
        ),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=opcoes,
    )


def test_dedupe_mesmo_plano_mesma_tabela_documentos_diferentes():
    rascunho = rascunho_vazio("lunvox", "Lunvox")
    valores = list(_PRATA_QC)
    for i in range(4):
        op = _opcao_pronta(
            opcao_id=f"op-qc-{i}",
            nome="PRATA QC COPART",
            valores=valores,
            acomodacao="Enfermaria",
            doc_hash=f"h{i}",
        )
        aplicar_extracao_confirmada(
            rascunho, _extracao(f"doc-{i}", f"ext-{i}", [op])
        )
    assert len(rascunho.opcoes_proposta) == 1
    op = rascunho.opcoes_proposta[0]
    assert op.plano_nome == "PRATA QC COPART"
    assert set(op.documentos_origem_ids) == {f"doc-{i}" for i in range(4)}


def test_mesmo_nome_tabela_diferente_alerta_sem_dedupe():
    rascunho = rascunho_vazio("lunvox", "Lunvox")
    op_a = _opcao_pronta(
        opcao_id="op-a",
        nome="PRATA QC COPART",
        valores=list(_PRATA_QC),
        acomodacao="Enfermaria",
    )
    op_b = _opcao_pronta(
        opcao_id="op-b",
        nome="PRATA QC COPART",
        valores=[v + 100 for v in _PRATA_QC],
        acomodacao="Enfermaria",
        doc_hash="h2",
    )
    _, b1 = aplicar_extracao_confirmada(rascunho, _extracao("doc-a", "ext-a", [op_a]))
    assert not b1
    _, b2 = aplicar_extracao_confirmada(rascunho, _extracao("doc-b", "ext-b", [op_b]))
    assert len(rascunho.opcoes_proposta) == 2
    assert any("tabela de valores diferente" in m for b in b2 for m in b["motivos"])


def test_alerta_acomodacao_divergente_matriz_comparativo_html(tmp_path: Path):
    rascunho = rascunho_vazio("aco", "Acomodação")
    rascunho.formato = "renovacao"
    rascunho.escolhas = EscolhasEstudo(
        data_referencia_idade=date(2026, 6, 30),
        baseline_escolhido=CampoConfirmavelBaseline(valor="reajustado", confirmado=True),
        precedencia_atual_vida=CampoConfirmavelPrecedencia(
            valor="tabela_atual", confirmado=True
        ),
    )
    rascunho.subgrupos_atuais = [
        SubgrupoAtualRascunho(
            id="sg-enf",
            operadora="Hapvida",
            plano_nome="SMART 400",
            acomodacao="Enfermaria",
            tipo_fiscal="operadora",
            regime_copart_id="regime-parcial",
            reajuste_bps=0,
            tabela_atual=[_faixa_atual(i) for i in range(10)],
        ),
        SubgrupoAtualRascunho(
            id="sg-apt",
            operadora="Hapvida",
            plano_nome="ADVANCE 600",
            acomodacao="Apartamento",
            tipo_fiscal="operadora",
            regime_copart_id="regime-parcial",
            reajuste_bps=0,
            tabela_atual=[_faixa_atual(i) for i in range(10)],
        ),
    ]
    rascunho.regimes_copart = [
        RegimeCopartRascunho(id="regime-parcial", tipo="parcial", percentual=30)
    ]
    rascunho.vidas = [
        VidaRascunho(
            id="v0",
            nome="Tit Enf",
            nascimento=date(1990, 1, 1),
            incluida=True,
            subgrupo_atual_id="sg-enf",
        ),
        VidaRascunho(
            id="v1",
            nome="Tit Apt",
            nascimento=date(1990, 1, 1),
            incluida=True,
            subgrupo_atual_id="sg-apt",
        ),
    ]
    op = _opcao_pronta(
        opcao_id="op-qc",
        nome="PRATA QC COPART",
        valores=list(_PRATA_QC),
        acomodacao="Enfermaria",
    )
    aplicar_extracao_confirmada(rascunho, _extracao("doc-1", "ext-1", [op]))
    sincronizar_cenarios(rascunho)
    from newport_app.rascunho.cenarios_sync import garantir_cenarios_uniformes_multi

    garantir_cenarios_uniformes_multi(rascunho)
    # Fixture uniforme: mesma proposta (QC) nos dois subgrupos → diverge no de apt
    msgs = coletar_divergencias_acomodacao(rascunho)
    assert msgs
    assert any("ADVANCE 600" in m and "Apartamento" in m and "Enfermaria" in m for m in msgs)
    assert any(p.codigo == "APP-ACO-001" for p in pendencias_divergencia_acomodacao(rascunho))
    assert any(p.codigo == "APP-ACO-001" for p in pendencias_compilacao(rascunho))

    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel and compilado.compilado
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    cmp = montar_comparativo(rascunho, motor_result=motor)
    assert any(p.codigo == "APP-ACO-001" for p in cmp.pendencias)

    db = tmp_path / "aco.db"
    repo = SQLiteStudyRepository(db)
    snap_svc = SnapshotService(repo, SnapshotRepository(db), HistoricoRepository(db))
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(
            revisor_nome="Ana", confirmo_conteudo=True, auto_aprovacao=False
        ),
    )
    snap = snap_svc.obter_snapshot(g.snapshot_id)
    vm = construir_view_model(
        snap, modo="faixas", propostas_selecionadas=[rascunho.opcoes_proposta[0].id]
    )
    assert vm.avisos_acomodacao
    html = render_html(vm)
    assert "aviso-acomodacao" in html
    assert "ADVANCE 600" in html
    assert "não é equivalente" in html


def _vidas_por_contagem(qtds: list[int], sg_id: str, prefixo: str) -> list[VidaRascunho]:
    # idades centrais por faixa (ref 2026-06-30)
    nascimentos = [
        date(2012, 6, 15),
        date(2005, 6, 15),
        date(2001, 6, 15),
        date(1995, 6, 15),
        date(1990, 6, 15),
        date(1985, 6, 15),
        date(1980, 6, 15),
        date(1975, 6, 15),
        date(1970, 6, 15),
        date(1960, 6, 15),
    ]
    vidas: list[VidaRascunho] = []
    n = 0
    for faixa, qtd in enumerate(qtds):
        for _ in range(qtd):
            vidas.append(
                VidaRascunho(
                    id=f"{prefixo}{n}",
                    nome=f"Benef {prefixo}{n}",
                    nascimento=nascimentos[faixa],
                    incluida=True,
                    subgrupo_atual_id=sg_id,
                )
            )
            n += 1
    return vidas


def test_lunvox_combo_por_acomodacao_totais():
    """Totais Amil 1–4 do estudo Lunvox com atribuição por acomodação."""
    rascunho = rascunho_vazio("lunvox-tot", "Lunvox totais")
    rascunho.formato = "renovacao"
    rascunho.escolhas = EscolhasEstudo(
        data_referencia_idade=date(2026, 6, 30),
        baseline_escolhido=CampoConfirmavelBaseline(valor="reajustado", confirmado=True),
        precedencia_atual_vida=CampoConfirmavelPrecedencia(
            valor="tabela_atual", confirmado=True
        ),
    )
    rascunho.regimes_copart = [
        RegimeCopartRascunho(id="regime-parcial", tipo="parcial", percentual=30)
    ]
    rascunho.subgrupos_atuais = [
        SubgrupoAtualRascunho(
            id="sg-smart",
            operadora="Hapvida",
            plano_nome="SMART 400",
            acomodacao="Enfermaria",
            tipo_fiscal="operadora",
            regime_copart_id="regime-parcial",
            reajuste_bps=0,
            tabela_atual=[_faixa_atual(i) for i in range(10)],
        ),
        SubgrupoAtualRascunho(
            id="sg-adv600",
            operadora="Hapvida",
            plano_nome="ADVANCE 600",
            acomodacao="Apartamento",
            tipo_fiscal="operadora",
            regime_copart_id="regime-parcial",
            reajuste_bps=0,
            tabela_atual=[_faixa_atual(i) for i in range(10)],
        ),
        SubgrupoAtualRascunho(
            id="sg-adv700",
            operadora="Hapvida",
            plano_nome="ADVANCE 700",
            acomodacao="Apartamento",
            tipo_fiscal="operadora",
            regime_copart_id="regime-parcial",
            reajuste_bps=0,
            tabela_atual=[_faixa_atual(i) for i in range(10)],
        ),
    ]
    # 31 enf + 8 apt + 8 apt = 47 (mesma massa do PDF)
    qtd_adv = [max(0, q // 2) for q in _QTD_QP]
    # ajustar para somar 16
    while sum(qtd_adv) < 16:
        for i in range(10):
            if sum(qtd_adv) >= 16:
                break
            if _QTD_QP[i] > qtd_adv[i]:
                qtd_adv[i] += 1
    qtd_adv700 = [_QTD_QP[i] - qtd_adv[i] for i in range(10)]
    rascunho.vidas = (
        _vidas_por_contagem(_QTD_QC, "sg-smart", "e")
        + _vidas_por_contagem(qtd_adv, "sg-adv600", "a6")
        + _vidas_por_contagem(qtd_adv700, "sg-adv700", "a7")
    )

    combos = [
        ("PRATA QP COPART", _PRATA_QP, 1_587_851),
        ("OURO QP R COPART", _OURO_QP, 1_751_381),
        ("PLATINUM R1 COPART", _PLAT_QP, 2_059_852),
        ("AMIL S750 R1 QP NAC COPART PJ", _S750_QP, 1_982_493),
    ]
    # Uma única PRATA QC compartilhada
    aplicar_extracao_confirmada(
        rascunho,
        _extracao(
            "doc-prata",
            "ext-prata",
            [
                _opcao_pronta(
                    opcao_id="op-qc",
                    nome="PRATA QC COPART",
                    valores=list(_PRATA_QC),
                    acomodacao="Enfermaria",
                ),
                _opcao_pronta(
                    opcao_id="op-qp-prata",
                    nome="PRATA QP COPART",
                    valores=list(_PRATA_QP),
                    acomodacao="Apartamento",
                ),
            ],
        ),
    )
    for i, (nome, vals, _) in enumerate(combos[1:], start=2):
        aplicar_extracao_confirmada(
            rascunho,
            _extracao(
                f"doc-{i}",
                f"ext-{i}",
                [
                    _opcao_pronta(
                        opcao_id=f"op-qc-{i}",
                        nome="PRATA QC COPART",
                        valores=list(_PRATA_QC),
                        acomodacao="Enfermaria",
                        doc_hash=f"h{i}",
                    ),
                    _opcao_pronta(
                        opcao_id=f"op-qp-{i}",
                        nome=nome,
                        valores=list(vals),
                        acomodacao="Apartamento",
                        doc_hash=f"h{i}",
                    ),
                ],
            ),
        )

    # QC deduplicado
    qc_ops = [o for o in rascunho.opcoes_proposta if o.plano_nome == "PRATA QC COPART"]
    assert len(qc_ops) == 1
    assert len(qc_ops[0].documentos_origem_ids) >= 2

    op_por_nome = {o.plano_nome: o for o in rascunho.opcoes_proposta}
    op_qc = op_por_nome["PRATA QC COPART"]
    totais = []
    for nome, _, esperado in combos:
        op_qp = op_por_nome[nome]
        rascunho.cenarios = [
            CenarioRascunho(
                id="c-combo",
                atribuicoes=[
                    AtribuicaoRascunho(
                        id="a1",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-smart",
                        opcao_plano_id=op_qc.id,
                    ),
                    AtribuicaoRascunho(
                        id="a2",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-adv600",
                        opcao_plano_id=op_qp.id,
                    ),
                    AtribuicaoRascunho(
                        id="a3",
                        alvo_tipo="subgrupo",
                        alvo_id="sg-adv700",
                        opcao_plano_id=op_qp.id,
                    ),
                ],
            )
        ]
        compilado = compile(rascunho, policy_registry=default_registry)
        assert compilado.compilavel and compilado.compilado, compilado.erros
        motor = calcular(
            compilado.compilado.estudo_input,
            compilado.compilado.effective_policy,
        )
        assert not motor.tem_bloqueio
        total = motor.cenarios[0].total_proposta_centavos.centavos
        totais.append(total)
        assert total == esperado, (nome, total, esperado)
        assert not coletar_divergencias_acomodacao(rascunho)

    assert totais == [1_587_851, 1_751_381, 2_059_852, 1_982_493]


def test_estudo_subgrupo_unico_inalterado():
    from newport_app.seed.ficticio import rascunho_demo_12_vidas

    rascunho = rascunho_demo_12_vidas()
    assert len(rascunho.subgrupos_atuais) == 1
    sincronizar_cenarios(rascunho)
    assert coletar_divergencias_acomodacao(rascunho) == []
    assert pendencias_divergencia_acomodacao(rascunho) == []


@pytest.mark.private_corpus
def test_lunvox_pdfs_reais_dedupe_prata_qc():
    pasta = _pasta_cotacoes()
    if pasta is None:
        pytest.skip("Lunvox indisponível")
    rascunho = rascunho_vazio("lunvox-pdf", "Lunvox PDF")
    for path in sorted(pasta.glob("AMIL*.pdf")):
        if "BLACK" in path.name.upper():
            continue
        with PdfDocumento.abrir(path.read_bytes()) as doc:
            ops, _, _ = amil.parse(doc, documento_hash=path.stem)
        for op in ops:
            normalizar_opcao(op, parser_versao=amil.PARSER_VERSAO, documento_hash=path.stem)
            if op.tipo_fiscal:
                op.tipo_fiscal.texto = "operadora"
                op.tipo_fiscal.confirmado = True
                op.tipo_fiscal.estado = "confirmar"
            if op.regime_copart:
                op.regime_copart.texto = op.regime_copart.texto or "parcial"
                op.regime_copart.confirmado = True
                op.regime_copart.estado = "confirmar"
            if op.operadora:
                op.operadora.confirmado = True
            if op.plano_nome:
                op.plano_nome.confirmado = True
            if op.acomodacao:
                op.acomodacao.confirmado = True
            for fx in op.tabela:
                fx.valor.confirmado = True
                if fx.quantidade:
                    fx.quantidade.confirmado = True
            op.selecionada_para_comparativo = True
            reconciliar_opcao(op)
        aplicar_extracao_confirmada(
            rascunho,
            ExtracaoCotacaoCandidata(
                id=f"ext-{path.stem}",
                estudo_id="lunvox-pdf",
                versao=1,
                documento=DocumentoCotacaoPDF(
                    id=f"doc-{path.stem}",
                    nome_arquivo=path.name,
                    hash_sha256=path.stem,
                    parser_versao=amil.PARSER_VERSAO,
                    operadora_detectada="Amil",
                ),
                estado="extraido",
                criado_em=datetime.now(timezone.utc),
                opcoes=ops,
            ),
        )
    qc = [o for o in rascunho.opcoes_proposta if o.plano_nome == "PRATA QC COPART"]
    assert len(qc) == 1
    assert len(qc[0].documentos_origem_ids) >= 3
