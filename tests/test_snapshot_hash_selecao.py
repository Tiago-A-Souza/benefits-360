"""Correção 2 — seleção de propostas no hash e invalidação ao alterar."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import SelecaoApresentacaoRascunho
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.snapshot import SnapshotService
from newport_app.snapshot.hashing import (
    CAMPOS_PAYLOAD_CANONICO,
    CAMPOS_PAYLOAD_CANONICO_2_7_0,
    hash_sha256_objeto,
    hash_snapshot_canonico,
)
from tests.test_comparativo_multiplas_propostas import _rascunho_quatro_propostas


def _hash_formato_2_7(conteudo: dict) -> str:
    return hash_sha256_objeto(
        {k: conteudo[k] for k in CAMPOS_PAYLOAD_CANONICO_2_7_0 if k in conteudo}
    )


def _stack(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    return repo, historico, snap_repo, snap_svc


def _rascunho_com_selecao(ordem: list[str]):
    r = _rascunho_quatro_propostas()
    r.selecao_apresentacao = SelecaoApresentacaoRascunho(
        opcao_ids=list(ordem),
        ordem=list(ordem),
    )
    return r


def test_selecoes_diferentes_produzem_hashes_diferentes(tmp_path: Path):
    repo, _, _, snap_svc = _stack(tmp_path)
    r = _rascunho_com_selecao(["op-1", "op-2"])
    repo.salvar_rascunho(r)
    h1 = snap_svc.gerar_snapshot_candidato(r.id).hash_sha256

    r = repo.obter_rascunho(r.id)
    assert r is not None
    r.selecao_apresentacao = SelecaoApresentacaoRascunho(
        opcao_ids=["op-1", "op-2", "op-3"],
        ordem=["op-1", "op-2", "op-3"],
    )
    repo.salvar_rascunho(r)
    h2 = snap_svc.gerar_snapshot_candidato(r.id).hash_sha256
    assert h1 != h2


def test_reordenar_selecao_muda_hash(tmp_path: Path):
    repo, _, _, snap_svc = _stack(tmp_path)
    r = _rascunho_com_selecao(["op-1", "op-2"])
    repo.salvar_rascunho(r)
    h1 = snap_svc.gerar_snapshot_candidato(r.id).hash_sha256

    r = repo.obter_rascunho(r.id)
    assert r is not None
    r.selecao_apresentacao = SelecaoApresentacaoRascunho(
        opcao_ids=["op-2", "op-1"],
        ordem=["op-2", "op-1"],
    )
    repo.salvar_rascunho(r)
    h2 = snap_svc.gerar_snapshot_candidato(r.id).hash_sha256
    assert h1 != h2


def test_payload_formato_anterior_mantem_hash(tmp_path: Path):
    repo, _, _, snap_svc = _stack(tmp_path)
    r = _rascunho_com_selecao(["op-1", "op-2"])
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)

    payload_anterior = dict(snap.payload)
    payload_anterior.pop("snapshot_versao", None)
    assert "propostas_apresentacao" in payload_anterior

    hash_antes = _hash_formato_2_7(payload_anterior)
    hash_depois = hash_snapshot_canonico(payload_anterior)
    assert hash_antes == hash_depois

    naive_atual = hash_sha256_objeto(
        {k: payload_anterior[k] for k in CAMPOS_PAYLOAD_CANONICO if k in payload_anterior}
    )
    assert naive_atual != hash_depois


def test_alterar_selecao_com_snapshot_aprovado_supera(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    client = TestClient(create_app(repo=repo, seed_demos=False))
    r = _rascunho_com_selecao(["op-1"])
    repo.salvar_rascunho(r)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, HistoricoRepository(db))
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )

    resp = client.put(
        f"/api/estudos/{r.id}/comparativo/selecao-apresentacao",
        json={"opcao_ids": ["op-1", "op-2"]},
    )
    assert resp.status_code == 200

    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    assert snap.estado == "superado"
    aprov = snap_repo.obter_aprovacao(gerado.snapshot_id)
    assert aprov is not None
    assert aprov.invalidada_em is not None


def test_alterar_selecao_sem_snapshot_nao_erra(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    client = TestClient(create_app(repo=repo, seed_demos=False))
    r = _rascunho_com_selecao(["op-1"])
    repo.salvar_rascunho(r)
    resp = client.put(
        f"/api/estudos/{r.id}/comparativo/selecao-apresentacao",
        json={"opcao_ids": ["op-2"]},
    )
    assert resp.status_code == 200
    assert resp.json()["ordem"] == ["op-2"]
