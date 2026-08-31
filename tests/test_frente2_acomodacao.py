"""Frente 2 — caminhos de preenchimento e alertas de acomodação."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.cotacao_pdf.apply import aplicar_extracao_confirmada
from newport_app.cotacao_pdf.conferencia import normalizar_opcao
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
    OpcaoPropostaRascunho,
    PriceBasisRascunho,
    RascunhoEstudo,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    VidaRascunho,
)
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.rascunho.acomodacao import (
    coletar_divergencias_acomodacao,
    coletar_incompletos_acomodacao,
    pendencias_divergencia_acomodacao,
    pendencias_incompleto_acomodacao,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import _faixa_atual
from newport_app.services.extracao_cotacao import ExtracaoCotacaoService
from newport_app.services.snapshot import SnapshotService
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_app.siscor_mapper.apply import rascunho_vazio
from newport_motor.engine import calcular
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)
from tests.test_acomodacao_dedupe import _extracao, _opcao_pronta
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento


def _rascunho_base_renovacao() -> RascunhoEstudo:
    rascunho = rascunho_vazio("f2", "Frente 2")
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
            tipo_fiscal="operadora",
            regime_copart_id="regime-parcial",
            reajuste_bps=0,
            tabela_atual=[_faixa_atual(i) for i in range(10)],
        ),
        SubgrupoAtualRascunho(
            id="sg-apt",
            operadora="Hapvida",
            plano_nome="ADVANCE 600",
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
        valores=[20_000 + i * 100 for i in range(10)],
        acomodacao=None,
    )
    aplicar_extracao_confirmada(rascunho, _extracao("doc-1", "ext-1", [op]))
    sincronizar_cenarios(rascunho)
    from newport_app.rascunho.cenarios_sync import garantir_cenarios_uniformes_multi

    garantir_cenarios_uniformes_multi(rascunho)
    return rascunho


def test_01_etapa2_persiste_acomodacao_plano_vigente(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "f2.db")
    rascunho = _rascunho_base_renovacao()
    rascunho.subgrupos_atuais[0].acomodacao = "enfermaria"
    rascunho.subgrupos_atuais[1].acomodacao = "apartamento"
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert salvo.subgrupos_atuais[0].acomodacao == "enfermaria"
    assert salvo.subgrupos_atuais[1].acomodacao == "apartamento"


def test_02_conferencia_pdf_persiste_acomodacao_opcao(tmp_path: Path):
    extracao = ExtracaoCotacaoCandidata(
        id="ext-ac",
        estudo_id="est-1",
        versao=1,
        documento=DocumentoCotacaoPDF(id="doc-1", nome_arquivo="t.pdf", hash_sha256="h"),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=[],
    )
    op = OpcaoCotacaoCandidata(id="op-sul", selecionada_para_comparativo=True)
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    op.operadora.texto = "SulAmérica"
    op.plano_nome.texto = "Plano Sul"
    op.tipo_fiscal.texto = "seguradora"
    op.regime_copart.texto = "sem"
    extracao.opcoes.append(op)

    repo = ExtracaoCotacaoRepository(tmp_path / "ext.db")
    repo.salvar(extracao)

    class _EstudosVazio:
        pass

    svc = ExtracaoCotacaoService(_EstudosVazio(), repo, uploads_dir=tmp_path)  # type: ignore[arg-type]
    assert op.acomodacao is not None
    svc.atualizar_campo(
        "ext-ac",
        op.acomodacao.id,
        texto="apartamento",
        confirmado=True,
    )
    gravada = repo.obter_por_id("ext-ac")
    assert gravada is not None
    por_id = {o.id: o for o in gravada.opcoes}
    assert por_id["op-sul"].acomodacao.texto == "apartamento"
    assert por_id["op-sul"].acomodacao.confirmado is True


def test_03_divergencia_quando_ambos_preenchidos_e_diferentes():
    rascunho = _rascunho_base_renovacao()
    rascunho.subgrupos_atuais[1].acomodacao = "apartamento"
    rascunho.opcoes_proposta[0].acomodacao = "enfermaria"
    msgs = coletar_divergencias_acomodacao(rascunho)
    assert msgs
    assert any("ADVANCE 600" in m and "Apartamento" in m for m in msgs)
    assert any(p.codigo == "APP-ACO-001" for p in pendencias_divergencia_acomodacao(rascunho))


def test_04_incompleto_um_lado_vazio_nao_bloqueia():
    rascunho = _rascunho_base_renovacao()
    rascunho.subgrupos_atuais[1].acomodacao = "apartamento"
    incompletos = coletar_incompletos_acomodacao(rascunho)
    assert incompletos
    assert any("não informada" in m.lower() for m in incompletos)
    pends = pendencias_incompleto_acomodacao(rascunho)
    assert pends
    assert all(p.tipo == "info" and p.codigo == "APP-ACO-002" for p in pends)
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel and compilado.compilado
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    assert not motor.tem_bloqueio


def test_05_incompleto_quando_ambos_vazios():
    rascunho = _rascunho_base_renovacao()
    incompletos = coletar_incompletos_acomodacao(rascunho)
    assert incompletos
    assert any("nenhum dos lados informado" in m for m in incompletos)
    assert coletar_divergencias_acomodacao(rascunho) == []


def test_06_estudos_demo_sem_preenchimento_automatico(tmp_path: Path):
    db = Path(".data/newport_app.db")
    if not db.is_file():
        pytest.skip("banco demo ausente")
    repo_orig = SQLiteStudyRepository(db)
    repo_tmp = SQLiteStudyRepository(tmp_path / "roundtrip.db")
    for eid in repo_orig.listar_ids():
        r = repo_orig.obter_rascunho(eid)
        if not r:
            continue
        antes = {sg.id: sg.acomodacao for sg in r.subgrupos_atuais}
        repo_tmp.salvar_rascunho(r)
        salvo = repo_tmp.obter_rascunho(eid)
        assert salvo is not None
        depois = {sg.id: sg.acomodacao for sg in salvo.subgrupos_atuais}
        assert antes == depois


def test_07_gabarito_anistia_inalterado(tmp_path: Path):
    import json

    from tests.test_paridade_matriz_html import _GABARITO

    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"])
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_08_nenhum_valor_calculado_se_move(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz_antes, _ = _calcular_matriz(rascunho)
    totais_antes = {
        p.opcao_id: p.numerico.proposta_mensal_centavos
        for p in matriz_antes.propostas
        if p.calculo_realizado and p.numerico
    }
    for sg in rascunho.subgrupos_atuais:
        sg.acomodacao = sg.acomodacao or "enfermaria"
    for op in rascunho.opcoes_proposta:
        op.acomodacao = op.acomodacao or "enfermaria"
    matriz_depois, _ = _calcular_matriz(rascunho)
    totais_depois = {
        p.opcao_id: p.numerico.proposta_mensal_centavos
        for p in matriz_depois.propostas
        if p.calculo_realizado and p.numerico
    }
    assert totais_antes == totais_depois


def test_09_pendencias_incompleto_no_comparativo(tmp_path: Path):
    rascunho = _rascunho_base_renovacao()
    compilado = compile(rascunho, policy_registry=default_registry)
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    cmp = montar_comparativo(rascunho, motor_result=motor)
    assert any(p.codigo == "APP-ACO-002" for p in cmp.pendencias)
    assert not any(p.tipo == "bloqueio" and p.codigo == "APP-ACO-002" for p in cmp.pendencias)


def test_10_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    db = tmp_path / "hash.db"
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
    assert snap.hash_sha256 == h_antes


def test_contagem_alertas_incompleto_demo():
    """Diagnóstico: quantos estudos do demo passam a exibir incompleto."""
    db = Path(".data/newport_app.db")
    if not db.is_file():
        pytest.skip("banco demo ausente")
    repo = SQLiteStudyRepository(db)
    estudos_com_incompleto = 0
    pares_incompletos = 0
    for eid in repo.listar_ids():
        r = repo.obter_rascunho(eid)
        if not r or r.formato != "renovacao":
            continue
        msgs = coletar_incompletos_acomodacao(r)
        if msgs:
            estudos_com_incompleto += 1
            pares_incompletos += len(msgs)
    print(f"ESTUDOS_INCOMPLETO={estudos_com_incompleto}")
    print(f"PARES_INCOMPLETOS={pares_incompletos}")
    assert pares_incompletos >= 0
