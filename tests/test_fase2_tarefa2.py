"""FASE 2 · TAREFA 2 — exportação a partir do payload congelado."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.snapshot import AprovacaoSnapshot, GerarApresentacaoRequest, SnapshotCalculo
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.apresentacao import ApresentacaoService
from newport_app.services.snapshot import SnapshotFormatoIncompativelError, SnapshotService
from newport_app.snapshot.comparativo import (
    MENSAGEM_FORMATO_ANTERIOR,
    ler_comparativo_congelado,
)
from newport_motor.engine import calcular
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
    assert_paridade_observacao_faixas,
    assert_paridade_planos,
    assert_paridade_rotulos,
)

_MODOS = ("resumo", "faixas", "grupo_familiar")


def _stack(tmp_path: Path, nome: str = "fase2-t2"):
    db = tmp_path / f"{nome}.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    apres = ApresentacaoService(snap_svc, snap_repo, tmp_path / f"{nome}-html")
    return repo, snap_repo, snap_svc, apres


def _aprovar(repo, snap_svc, rascunho):
    from newport_app.models.snapshot import AprovarSnapshotRequest

    repo.salvar_rascunho(rascunho)
    gerado = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    return snap_svc.obter_snapshot(gerado.snapshot_id)


def _ids(matriz) -> list[str]:
    from newport_app.presentation.colisao_coluna import chave_de_coluna

    return [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]


def _calcular_ao_vivo(rascunho):
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel and compilado.compilado is not None
    motor = calcular(compilado.compilado.estudo_input, compilado.compilado.effective_policy)
    return montar_comparativo(rascunho, motor_result=motor)


def test_documento_idêntico_a_matriz_do_mesmo_snapshot(tmp_path: Path):
    repo, _, snap_svc, _ = _stack(tmp_path)
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(repo, snap_svc, rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    ids = _ids(matriz)
    vidas_matriz = {
        v.vida_id: v
        for p in matriz.propostas
        for sec in p.secoes
        for v in sec.vidas
    }

    for modo in _MODOS:
        vm = construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        for p in matriz.propostas:
            assert p.numerico is not None
            assert vm.totais_gerais.propostas[p.opcao_id] == p.numerico.proposta_mensal_centavos
        assert_paridade_rotulos(matriz, vm)
        if matriz.formato != "novo":
            assert_paridade_planos(matriz, vm)
        if modo == "faixas":
            assert_paridade_observacao_faixas(matriz, vm)
        if modo == "grupo_familiar":
            membros = [m for g in vm.grupos_familiares for m in g.membros]
            assert len(membros) == len(vidas_matriz)
            for b in membros:
                origem = vidas_matriz[b.vida_id]
                assert b.atual_vigente_centavos == origem.vigente_centavos
                assert b.atual_reajustado_centavos == origem.reajustado_centavos
                for col in b.propostas:
                    prop = next(
                        p
                        for p in matriz.propostas
                        if p.cenario_id == (col.coluna_id or col.opcao_id)
                        or p.opcao_id == col.opcao_id
                    )
                    vd = next(
                        v
                        for sec in prop.secoes
                        for v in sec.vidas
                        if v.vida_id == b.vida_id
                    )
                    assert col.valor_centavos == vd.proposta_centavos


def test_alterar_rascunho_nao_altera_exportacao_do_snapshot(tmp_path: Path):
    repo, _, snap_svc, apres = _stack(tmp_path, "rascunho-depois")
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(repo, snap_svc, rascunho)
    total_congelado = ler_comparativo_congelado(snap.payload).propostas[0].numerico
    assert total_congelado is not None
    valor_snap = total_congelado.proposta_mensal_centavos

    vivo = repo.obter_rascunho(rascunho.id)
    assert vivo is not None
    op = vivo.opcoes_proposta[0]
    vivo.opcoes_proposta[0] = op.model_copy(
        update={
            "tabela": [
                f.model_copy(update={"valor_centavos": f.valor_centavos + 250_000})
                for f in op.tabela
            ]
        }
    )
    repo.salvar_rascunho(vivo)
    live = _calcular_ao_vivo(vivo)
    assert live.propostas[0].numerico is not None
    assert live.propostas[0].numerico.proposta_mensal_centavos != valor_snap

    snap_reaberto = snap_svc.obter_snapshot(snap.id)
    for modo in _MODOS:
        vm = construir_view_model(
            snap_reaberto, modo=modo, propostas_selecionadas=["op-1"]
        )
        assert vm.totais_gerais.propostas["op-1"] == valor_snap
        html = render_html(vm)
        assert "RASCUNHO INTERNO" in html

    res = apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
    )
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    assert "RASCUNHO INTERNO" in html


def test_formato_anterior_recusa_html_com_a_mesma_mensagem(tmp_path: Path):
    _, snap_repo, snap_svc, apres = _stack(tmp_path, "legado")
    snap_id = "snap-legado"
    estudo_id = "est-legado"
    snap_repo.salvar_snapshot(
        SnapshotCalculo(
            id=snap_id,
            estudo_id=estudo_id,
            estado="aprovado",
            hash_sha256="abc",
            payload={
                "comparativo": {
                    "estudo_id": estudo_id,
                    "titulo": "Renovação",
                    "beneficiarios_calculados": 12,
                    "calculo_realizado": True,
                    "formato": "renovacao",
                    "plano_atual": {"operadora": "AMIL", "plano_nome": "S750"},
                }
            },
            compiler_versao="x",
            motor_versao="0.1.0",
            policy_set_versao="p",
            snapshot_versao=None,
            criado_em=datetime.now(timezone.utc),
        )
    )
    snap_repo.salvar_aprovacao(
        AprovacaoSnapshot(
            id=str(uuid.uuid4()),
            snapshot_id=snap_id,
            revisor_nome="Ana",
            aprovado_em=datetime.now(timezone.utc),
        )
    )
    with pytest.raises(SnapshotFormatoIncompativelError) as exc:
        apres.gerar_html(
            estudo_id,
            snap_id,
            GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
        )
    assert str(exc.value) == MENSAGEM_FORMATO_ANTERIOR
    with pytest.raises(SnapshotFormatoIncompativelError) as exc_vm:
        construir_view_model(
            snap_svc.obter_snapshot(snap_id),
            modo="resumo",
            propostas_selecionadas=["op-1"],
        )
    assert str(exc_vm.value) == MENSAGEM_FORMATO_ANTERIOR
    with pytest.raises(SnapshotFormatoIncompativelError) as exc_cmp:
        snap_svc.comparativo_do_snapshot(snap_id)
    assert str(exc_cmp.value) == MENSAGEM_FORMATO_ANTERIOR


def test_anistia_dois_planos_exporta_nos_tres_modos(tmp_path: Path):
    repo, _, snap_svc, _ = _stack(tmp_path, "anistia")
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(repo, snap_svc, rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    assert len(matriz.planos_atuais) == 2
    nomes = {p.plano_nome for p in matriz.planos_atuais}
    ids = _ids(matriz)
    for modo in _MODOS:
        vm = construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        planos_vm = [
            p
            for s in vm.secoes_regime
            for p in s.planos_atuais
            if p.subgrupo_id != "vidas-incluidas"
        ]
        assert {p.subgrupo_id for p in planos_vm} == {"sg-a", "sg-b"}
        html = render_html(vm)
        for nome in nomes:
            assert nome in html
        assert "RASCUNHO INTERNO" in html


def test_ivtec_seguro_novo_exporta_faixas_estudo_sem_contrato_atual(tmp_path: Path):
    repo, _, snap_svc, _ = _stack(tmp_path, "ivtec")
    rascunho = _rascunho_ivtec_novo()
    snap = _aprovar(repo, snap_svc, rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    assert matriz.planos_atuais == []
    assert matriz.faixas_estudo
    ids = _ids(matriz)
    faixas_origem = {fx.faixa for fx in matriz.faixas_estudo}
    for modo in _MODOS:
        vm = construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        assert vm.formato == "novo"
        assert vm.totais_gerais.atual_centavos is None
        html = render_html(vm)
        assert "Atual vigente" not in html
        assert "Atual reajustado" not in html
        assert "Contrato atual" not in html
        if modo == "faixas":
            faixas_vm = {
                fx.faixa
                for p in vm.secoes_regime[0].planos_atuais
                for fx in p.faixas
            }
            assert faixas_vm == faixas_origem


def test_gabarito_prata_e_ouro_preservado(tmp_path: Path):
    repo, _, snap_svc, _ = _stack(tmp_path, "gabarito")
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(repo, snap_svc, rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    ids = _ids(matriz)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_gabarito_propostas(matriz, vm, gab)
    prata = next(s for s in gab["propostas"] if s["chave"] == "prata")
    ouro = next(s for s in gab["propostas"] if s["chave"] == "ouro")
    assert prata["plano_a_centavos"] == 2_360_717
    assert prata["plano_b_centavos"] == 610_061
    assert ouro["plano_a_centavos"] == 2_751_249
    assert ouro["plano_b_centavos"] == 710_988
    html_r = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )
    assert "23.607,17" in html_r
    assert "6.100,61" in html_r
    assert "27.512,49" in html_r
    assert "7.109,88" in html_r


def test_modo_grupo_familiar_mantem_aviso_de_dados_pessoais(tmp_path: Path):
    repo, _, snap_svc, apres = _stack(tmp_path, "pii")
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(repo, snap_svc, rascunho)
    res = apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="grupo_familiar", propostas_selecionadas=["op-1"]),
    )
    assert res.aviso_dados_pessoais
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    assert "nomes de beneficiários" in html.lower()
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=["op-1"])
    assert "nomes de beneficiários" in render_html(vm).lower()
    # Legado beneficiario continua legível.
    res_leg = apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="beneficiario", propostas_selecionadas=["op-1"]),
    )
    assert res_leg.aviso_dados_pessoais


def test_banner_rascunho_interno_nos_tres_modos(tmp_path: Path):
    repo, _, snap_svc, _ = _stack(tmp_path, "banner")
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(repo, snap_svc, rascunho)
    for modo in _MODOS:
        html = render_html(
            construir_view_model(snap, modo=modo, propostas_selecionadas=["op-1"])
        )
        assert "RASCUNHO INTERNO" in html
        assert "políticas provisórias" in html.lower()
