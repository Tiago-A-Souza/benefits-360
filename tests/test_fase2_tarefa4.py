"""FASE 2 · TAREFA 4 — etapa 6 sai da navegação; GET de governança só lê."""

from __future__ import annotations

import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.snapshot import (
    AprovacaoSnapshot,
    AprovarSnapshotRequest,
    GerarApresentacaoRequest,
    SnapshotCalculo,
)
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA, construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.migration import reparar_aprovacoes_vivas_duplicadas
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.apresentacao import ApresentacaoService
from newport_app.services.calculo import CalculoService
from newport_app.services.snapshot import AprovacaoInvalidaError, SnapshotService
from newport_app.snapshot.comparativo import MENSAGEM_FORMATO_ANTERIOR, ler_comparativo_congelado
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)

_MODOS = ("resumo", "faixas", "grupo_familiar")


def _stack(tmp_path: Path, nome: str = "fase2-t4"):
    db = tmp_path / f"{nome}.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)

    def _invalidar(estudo_id: str, motivo: str) -> None:
        snap_svc.invalidar_por_alteracao(estudo_id, motivo)

    calc = CalculoService(
        repo,
        on_rascunho_alterado=_invalidar,
        snapshot_service=snap_svc,
    )
    apres = ApresentacaoService(snap_svc, snap_repo, tmp_path / f"{nome}-html")
    return repo, historico, snap_repo, snap_svc, calc, apres, db


def _client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def _ids_propostas(body: dict) -> list[str]:
    ordem = body.get("propostas_apresentacao") or []
    if ordem:
        return list(ordem)
    return [p["opcao_id"] for p in body.get("propostas") or [] if p.get("opcao_id")] or [
        "op-1"
    ]


def _confirmar(client: TestClient, estudo_id: str, opcao_ids: list[str] | None = None):
    calc = client.post(f"/api/estudos/{estudo_id}/calcular")
    assert calc.status_code == 200, calc.text
    body = calc.json()
    assert body["calculo_realizado"] is True
    ids = opcao_ids or _ids_propostas(body)
    conf = client.post(
        f"/api/estudos/{estudo_id}/comparativo/confirmar",
        json={"hash_comparativo": body["hash_comparativo"], "opcao_ids": ids},
    )
    return conf, body


def _aprovar_via_repo(snap_repo, snapshot_id: str, revisor: str, quando: datetime) -> None:
    snap_repo.marcar_aprovado(snapshot_id)
    snap_repo.salvar_aprovacao(
        AprovacaoSnapshot(
            id=str(uuid.uuid4()),
            snapshot_id=snapshot_id,
            revisor_nome=revisor,
            aprovado_em=quando,
        )
    )


def _duas_aprovacoes_vivas(repo, snap_repo, snap_svc, rascunho):
    repo.salvar_rascunho(rascunho)
    g1 = snap_svc.gerar_snapshot_candidato(rascunho.id)
    agora = datetime.now(timezone.utc)
    _aprovar_via_repo(snap_repo, g1.snapshot_id, "Ana", agora - timedelta(days=1))
    s1 = snap_svc.obter_snapshot(g1.snapshot_id)
    s2 = SnapshotCalculo(
        id=str(uuid.uuid4()),
        estudo_id=rascunho.id,
        estado="candidato",
        hash_sha256=s1.hash_sha256,
        payload=s1.payload,
        compiler_versao=s1.compiler_versao,
        motor_versao=s1.motor_versao,
        policy_set_versao=s1.policy_set_versao,
        snapshot_versao=s1.snapshot_versao,
        tem_bloqueio=False,
        criado_em=agora,
    )
    snap_repo.salvar_snapshot(s2)
    _aprovar_via_repo(snap_repo, s2.id, "Bruno", agora)
    return g1.snapshot_id, s2.id


def _rascunho_cinco_propostas():
    r = rascunho_demo_12_vidas()
    r.id = "t4-cinco"
    base = r.opcoes_proposta[0]
    r.opcoes_proposta = []
    for i in range(5):
        op = base.model_copy(deep=True)
        op.id = f"op-{i + 1}"
        op.plano_nome = f"Proposta Extra {i + 1}"
        r.opcoes_proposta.append(op)
    sincronizar_cenarios(r)
    return r


def _ths_por_tabela(html: str) -> list[int]:
    counts: list[int] = []
    for bloco in html.split("<table>")[1:]:
        cabeca = bloco.split("</thead>")[0]
        counts.append(cabeca.count("<th>"))
    return counts


def test_01_exportar_sem_aprovar_recusado(tmp_path: Path):
    repo, _, _, snap_svc, _, apres, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t4-b01"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    with pytest.raises(AprovacaoInvalidaError, match="aprovados"):
        apres.gerar_html(
            r.id,
            gerado.snapshot_id,
            GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
        )


def test_02_aprovar_sem_atestado_recusado(tmp_path: Path):
    repo, _, _, snap_svc, _, _, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t4-atestado"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    with pytest.raises(AprovacaoInvalidaError, match="revisou"):
        snap_svc.aprovar_snapshot(
            r.id,
            gerado.snapshot_id,
            AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=False),
        )


def test_03_exportar_snapshot_superado_recusado(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, apres, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t4-superado"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap_svc.invalidar_por_alteracao(r.id, "Rascunho alterado")
    assert snap_svc.obter_snapshot(gerado.snapshot_id).estado == "superado"
    with pytest.raises(AprovacaoInvalidaError):
        apres.gerar_html(
            r.id,
            gerado.snapshot_id,
            GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
        )
    assert snap_repo.obter_aprovacao(gerado.snapshot_id).invalidada_em is not None


def test_04_fluxo_completo_sem_etapa_6(tmp_path: Path):
    repo, _, _, _, _, _, _ = _stack(tmp_path, "fluxo")
    r = rascunho_demo_12_vidas()
    r.id = "t4-fluxo"
    repo.salvar_rascunho(r)
    client = _client(repo)
    conf, _ = _confirmar(client, r.id)
    assert conf.status_code == 200, conf.text
    body = conf.json()
    assert body.get("snapshot_id")
    # Não passa por POST /snapshot avulso — o freeze nasceu na confirmação.
    apr = client.post(
        f"/api/estudos/{r.id}/snapshots/{body['snapshot_id']}/aprovar",
        json={"revisor_nome": "Ana", "confirmo_conteudo": True},
    )
    assert apr.status_code == 200, apr.text
    ger = client.post(
        f"/api/estudos/{r.id}/snapshots/{body['snapshot_id']}/apresentacao/gerar",
        json={"modo": "resumo", "propostas_selecionadas": []},
    )
    assert ger.status_code == 200, ger.text
    assert ger.json()["entregavel_id"]
    html = client.get(
        f"/api/estudos/{r.id}/entregaveis/{ger.json()['entregavel_id']}/html"
    )
    assert html.status_code == 200
    assert "text/html" in html.headers.get("content-type", "")


def test_05_formato_anterior_abre_com_mensagem(tmp_path: Path):
    repo, _, snap_repo, _, _, _, _ = _stack(tmp_path, "fmt")
    r = rascunho_demo_12_vidas()
    r.id = "est-legado-t4"
    repo.salvar_rascunho(r)
    snap_id = "snap-legado-t4"
    snap_repo.salvar_snapshot(
        SnapshotCalculo(
            id=snap_id,
            estudo_id=r.id,
            estado="aprovado",
            hash_sha256="abc",
            payload={
                "comparativo": {
                    "estudo_id": r.id,
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
    client = _client(repo)
    status = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert status.status_code == 200
    body = status.json()
    assert body["aprovado"] is True
    assert body["formato_incompativel"] is True
    assert body["mensagem_formato"] == MENSAGEM_FORMATO_ANTERIOR
    assert "formato anterior" in body["mensagem_formato"].lower()
    assert body["aprovacao"]["revisor_nome"] == "Ana"
    preview = client.post(
        f"/api/estudos/{r.id}/snapshots/{snap_id}/apresentacao/preview",
        json={"modo": "resumo", "propostas_selecionadas": ["op-1"]},
    )
    assert preview.status_code == 422
    assert "formato anterior" in str(preview.json()).lower()


def test_06_anistia_exporta_tres_modos_dois_planos(tmp_path: Path):
    repo, _, _, snap_svc, _, _, _ = _stack(tmp_path, "anistia")
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    repo.salvar_rascunho(rascunho)
    gerado = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    matriz = ler_comparativo_congelado(snap.payload)
    assert len(matriz.planos_atuais) == 2
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    nomes = {p.plano_nome for p in matriz.planos_atuais}
    for modo in _MODOS:
        html = render_html(
            construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        )
        for nome in nomes:
            assert nome in html


def test_07_ivtec_exporta_sem_coluna_contrato_atual(tmp_path: Path):
    repo, _, _, snap_svc, _, _, _ = _stack(tmp_path, "ivtec")
    rascunho = _rascunho_ivtec_novo()
    repo.salvar_rascunho(rascunho)
    gerado = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    matriz = ler_comparativo_congelado(snap.payload)
    assert matriz.planos_atuais == []
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    for modo in _MODOS:
        html = render_html(
            construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        )
        assert "Contrato atual" not in html
        assert "Atual vigente" not in html


def test_08_gabarito_preservado(tmp_path: Path):
    repo, _, _, snap_svc, _, _, _ = _stack(tmp_path, "gabarito")
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    repo.salvar_rascunho(rascunho)
    gerado = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    matriz = ler_comparativo_congelado(snap.payload)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_gabarito_propostas(matriz, vm, gab)
    html_r = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )
    assert "23.607,17" in html_r
    assert "6.100,61" in html_r
    assert "27.512,49" in html_r
    assert "7.109,88" in html_r


def test_09_cinco_propostas_nao_corta_coluna(tmp_path: Path):
    repo, _, _, snap_svc, _, apres, _ = _stack(tmp_path, "cinco")
    r = _rascunho_cinco_propostas()
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    ids = [f"op-{i}" for i in range(1, 6)]
    nomes = [f"Proposta Extra {i}" for i in range(1, 6)]
    assert MAX_PROPOSTAS_POR_PAGINA == 3
    for modo in _MODOS:
        vm = construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        html = render_html(vm)
        for nome in nomes:
            assert nome in html, f"{nome} ausente no modo {modo}"
        if modo == "faixas":
            for secao in vm.secoes_regime:
                assert all(
                    len(p.propostas_ids) <= MAX_PROPOSTAS_POR_PAGINA
                    for p in secao.paginas_faixas
                )
                cobertos = [i for p in secao.paginas_faixas for i in p.propostas_ids]
                assert cobertos == ids
        if modo == "resumo":
            for n_th in _ths_por_tabela(html):
                # Indicador + contrato atual + no máximo 3 propostas
                assert n_th <= 2 + MAX_PROPOSTAS_POR_PAGINA
    res = apres.gerar_html(
        r.id,
        snap.id,
        GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=ids),
    )
    html_arquivo = (apres._entregaveis_dir / res.caminho_relativo).read_text(
        encoding="utf-8"
    )
    for nome in nomes:
        assert nome in html_arquivo


def test_get_nao_grava_duas_vivas(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, _, db = _stack(tmp_path, "get-ro")
    r = rascunho_demo_12_vidas()
    r.id = "t4-get-ro"
    id_antiga, id_nova = _duas_aprovacoes_vivas(repo, snap_repo, snap_svc, r)
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2
    client = _client(repo)
    a = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    b = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["snapshot_id"] == b.json()["snapshot_id"] == id_nova
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2
    with sqlite3.connect(db) as conn:
        aud = conn.execute(
            "SELECT COUNT(*) FROM auditoria WHERE acao='reparar_aprovacao_unica'"
        ).fetchone()[0]
    assert aud == 0
    assert id_antiga != id_nova


def test_gets_concorrentes_convergem(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, _, _ = _stack(tmp_path, "get-par")
    r = rascunho_demo_12_vidas()
    r.id = "t4-get-par"
    _, id_nova = _duas_aprovacoes_vivas(repo, snap_repo, snap_svc, r)
    client = _client(repo)

    def _get():
        return client.get(f"/api/estudos/{r.id}/snapshot-aprovado")

    with ThreadPoolExecutor(max_workers=4) as pool:
        respostas = list(pool.map(lambda _: _get(), range(8)))
    ids = {res.json()["snapshot_id"] for res in respostas}
    assert ids == {id_nova}
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2


def test_migracao_283_repara_e_audita(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, apres, db = _stack(tmp_path, "mig283")
    r = rascunho_demo_12_vidas()
    r.id = "t4-mig"
    id_antiga, id_nova = _duas_aprovacoes_vivas(repo, snap_repo, snap_svc, r)
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2
    with sqlite3.connect(db) as conn:
        n = reparar_aprovacoes_vivas_duplicadas(conn)
        conn.commit()
        aud = conn.execute(
            """
            SELECT acao, criado_por, entidade_id FROM auditoria
            WHERE estudo_id=? AND acao='reparar_aprovacao_unica'
            """,
            (r.id,),
        ).fetchone()
    assert n == 1
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 1
    vivo = snap_repo.snapshot_aprovado_atual(r.id)
    assert vivo is not None and vivo.id == id_nova
    assert aud is not None
    assert aud[1] == "migracao-2.8.3"
    assert aud[2] == id_nova
    assert snap_svc.obter_snapshot(id_antiga).estado == "superado"
    with pytest.raises(AprovacaoInvalidaError):
        apres.gerar_html(
            r.id,
            id_antiga,
            GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
        )
    res = apres.gerar_html(
        r.id,
        id_nova,
        GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
    )
    assert res.entregavel_id
    with sqlite3.connect(db) as conn:
        assert reparar_aprovacoes_vivas_duplicadas(conn) == 0
