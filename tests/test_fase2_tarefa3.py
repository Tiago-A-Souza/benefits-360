"""FASE 2 · TAREFA 3 — snapshot na confirmação e aprovação em vigor na etapa 5."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.responses import PendenciaItem
from newport_app.models.snapshot import (
    AprovacaoSnapshot,
    AprovarSnapshotRequest,
    GerarApresentacaoRequest,
    SnapshotCalculo,
)
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.apresentacao import ApresentacaoService
from newport_app.services.calculo import CalculoService
from newport_app.services.comparativo_confirmacao import comparativo_revisao_confirmada
from newport_app.services.snapshot import (
    AprovacaoInvalidaError,
    SnapshotBloqueadoError,
    SnapshotService,
)


def _stack(tmp_path: Path, nome: str = "fase2-t3"):
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
    return repo, historico, snap_repo, snap_svc, calc, apres


def _client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def _ids_propostas(body: dict) -> list[str]:
    ordem = body.get("propostas_apresentacao") or []
    if ordem:
        return list(ordem)
    return [p["opcao_id"] for p in body.get("propostas") or [] if p.get("opcao_id")] or [
        "op-1"
    ]


def _confirmar(client: TestClient, estudo_id: str):
    calc = client.post(f"/api/estudos/{estudo_id}/calcular")
    assert calc.status_code == 200, calc.text
    body = calc.json()
    assert body["calculo_realizado"] is True
    conf = client.post(
        f"/api/estudos/{estudo_id}/comparativo/confirmar",
        json={
            "hash_comparativo": body["hash_comparativo"],
            "opcao_ids": _ids_propostas(body),
        },
    )
    return conf


def _aprovar_via_repo(
    snap_repo: SnapshotRepository,
    snapshot_id: str,
    revisor: str,
    quando: datetime,
) -> None:
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
    """Simula o legado em que aprovar não superava a anterior."""
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


def test_01_exportar_sem_aprovar_recusado(tmp_path: Path):
    repo, _, _, snap_svc, _, apres = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-b01"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    with pytest.raises(AprovacaoInvalidaError, match="aprovados"):
        apres.gerar_html(
            r.id,
            gerado.snapshot_id,
            GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
        )


def test_02_aprovar_sem_atestado_recusado(tmp_path: Path):
    repo, _, _, snap_svc, _, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-atestado"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    with pytest.raises(AprovacaoInvalidaError, match="revisou"):
        snap_svc.aprovar_snapshot(
            r.id,
            gerado.snapshot_id,
            AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=False),
        )


def test_03_exportar_snapshot_superado_recusado(tmp_path: Path):
    repo, _, _, snap_svc, calc, apres = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-superado-exp"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    r2 = repo.obter_rascunho(r.id)
    assert r2 is not None
    r2.titulo = "Título alterado após aprovação"
    calc.salvar_rascunho(r2)
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    assert snap.estado == "superado"
    with pytest.raises(AprovacaoInvalidaError):
        apres.gerar_html(
            r.id,
            gerado.snapshot_id,
            GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
        )


def test_04_confirmar_gera_candidato_com_hash(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_12_vidas()
    r.id = "t3-confirm-snap"
    repo.salvar_rascunho(r)
    res = _confirmar(client, r.id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["snapshot_id"]
    assert body["hash_comparativo"]
    salvo = repo.obter_rascunho(r.id)
    assert salvo is not None
    assert comparativo_revisao_confirmada(salvo)
    snap_repo = SnapshotRepository(tmp_path / "t3.db")
    snap = snap_repo.obter_snapshot(body["snapshot_id"])
    assert snap is not None
    assert snap.estado == "candidato"
    assert snap.hash_sha256 == body["hash_comparativo"]
    assert salvo.confirmacao_comparativo.hash_comparativo == snap.hash_sha256


def test_05_falha_snapshot_nao_grava_confirmacao(tmp_path: Path, monkeypatch):
    def boom(self, estudo_id, rascunho=None):
        raise SnapshotBloqueadoError(
            "Não é possível congelar o comparativo — pendência: Valores não conferem"
        )

    monkeypatch.setattr(SnapshotService, "gerar_snapshot_candidato", boom)
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_12_vidas()
    r.id = "t3-atomico"
    repo.salvar_rascunho(r)
    res = _confirmar(client, r.id)
    assert res.status_code == 422, res.text
    assert "Valores não conferem" in res.text
    salvo = repo.obter_rascunho(r.id)
    assert salvo is not None
    assert salvo.confirmacao_comparativo is None


def test_06_h01_41_vidas_confirma_e_congela(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_41_vidas()
    repo.salvar_rascunho(r)
    res = _confirmar(client, r.id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["snapshot_id"]
    snap_repo = SnapshotRepository(tmp_path / "t3.db")
    snap = snap_repo.obter_snapshot(body["snapshot_id"])
    assert snap is not None
    assert snap.estado == "candidato"
    pendencias = snap.payload["comparativo"].get("pendencias", [])
    assert any(p.get("tipo") == "alerta" for p in pendencias)


def test_07_bloqueio_real_nomeia_pendencia(tmp_path: Path, monkeypatch):
    original = SnapshotService._compilar_e_calcular

    def com_bloqueio(self, rascunho):
        comparativo, payload, nucleo, _ = original(self, rascunho)
        comparativo = comparativo.model_copy(
            update={
                "pendencias": list(comparativo.pendencias)
                + [
                    PendenciaItem(
                        tipo="bloqueio",
                        titulo="Valores não conferem",
                        descricao="Total informado fora da tolerância.",
                    )
                ]
            }
        )
        return comparativo, payload, nucleo, True

    monkeypatch.setattr(SnapshotService, "_compilar_e_calcular", com_bloqueio)
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_12_vidas()
    r.id = "t3-bloqueio"
    repo.salvar_rascunho(r)
    res = _confirmar(client, r.id)
    assert res.status_code == 422, res.text
    assert "Valores não conferem" in res.text
    salvo = repo.obter_rascunho(r.id)
    assert salvo is not None
    assert salvo.confirmacao_comparativo is None


def test_08_alterar_rascunho_supera_e_avisa_etapa5(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_12_vidas()
    r.id = "t3-caiu"
    repo.salvar_rascunho(r)
    conf = _confirmar(client, r.id)
    assert conf.status_code == 200, conf.text
    snap_id = conf.json()["snapshot_id"]
    apr = client.post(
        f"/api/estudos/{r.id}/snapshots/{snap_id}/aprovar",
        json={"revisor_nome": "Ana", "confirmo_conteudo": True},
    )
    assert apr.status_code == 200, apr.text
    salvo = repo.obter_rascunho(r.id)
    assert salvo is not None
    salvo.titulo = "Reajuste alterado na etapa 2"
    app = create_app(repo=repo, seed_demos=False)
    app.state.calculo_service.salvar_rascunho(salvo)
    status = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert status.status_code == 200
    body = status.json()
    assert body["aprovado"] is False
    assert body["estado"] == "superado"
    assert body["superado"]["revisor_nome"] == "Ana"
    assert body["superado"]["aprovado_em"]
    snap = SnapshotRepository(tmp_path / "t3.db").obter_snapshot(snap_id)
    assert snap is not None
    assert snap.estado == "superado"
    assert repo.obter_rascunho(r.id).confirmacao_comparativo is None


def test_reconfirmar_e_reaprovar_depois_da_aprovacao_cair(tmp_path: Path):
    """Voltar à etapa 4 salva o rascunho: a aprovação cai e a confirmação
    tem de ser refeita — senão o botão da etapa 5 fica bloqueado."""
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_12_vidas()
    r.id = "t3-reaprovar"
    repo.salvar_rascunho(r)
    conf = _confirmar(client, r.id)
    assert conf.status_code == 200, conf.text
    snap_id = conf.json()["snapshot_id"]
    apr = client.post(
        f"/api/estudos/{r.id}/snapshots/{snap_id}/aprovar",
        json={"revisor_nome": "Ana", "confirmo_conteudo": True},
    )
    assert apr.status_code == 200, apr.text
    assert comparativo_revisao_confirmada(repo.obter_rascunho(r.id))

    salvo = repo.obter_rascunho(r.id)
    app = create_app(repo=repo, seed_demos=False)
    app.state.calculo_service.salvar_rascunho(salvo)

    status = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert status.status_code == 200
    assert status.json()["estado"] == "superado"
    assert status.json()["aprovado"] is False
    assert repo.obter_rascunho(r.id).confirmacao_comparativo is None

    calc = client.post(f"/api/estudos/{r.id}/calcular")
    assert calc.status_code == 200, calc.text
    body = calc.json()
    assert body["calculo_realizado"] is True
    conf2 = client.post(
        f"/api/estudos/{r.id}/comparativo/confirmar",
        json={
            "hash_comparativo": body["hash_comparativo"],
            "opcao_ids": _ids_propostas(body),
        },
    )
    assert conf2.status_code == 200, conf2.text
    novo_id = conf2.json()["snapshot_id"]
    assert novo_id != snap_id
    st2 = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert st2.json()["estado"] == "candidato"
    assert st2.json()["snapshot_id"] == novo_id

    apr2 = client.post(
        f"/api/estudos/{r.id}/snapshots/{novo_id}/aprovar",
        json={"revisor_nome": "Ana", "confirmo_conteudo": True},
    )
    assert apr2.status_code == 200, apr2.text
    st3 = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert st3.json()["aprovado"] is True
    assert st3.json()["estado"] == "aprovado"


def test_reconfirmar_com_confirmacao_orfa_snapshot_superado(tmp_path: Path):
    """Estudo já travado: confirmação ainda no rascunho, snapshot superado."""
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    snap_repo = SnapshotRepository(tmp_path / "t3.db")
    client = _client(repo)
    r = rascunho_demo_12_vidas()
    r.id = "t3-orfa"
    repo.salvar_rascunho(r)
    conf = _confirmar(client, r.id)
    assert conf.status_code == 200, conf.text
    snap_id = conf.json()["snapshot_id"]
    apr = client.post(
        f"/api/estudos/{r.id}/snapshots/{snap_id}/aprovar",
        json={"revisor_nome": "tt", "confirmo_conteudo": True},
    )
    assert apr.status_code == 200, apr.text
    snap_repo.invalidar_aprovacoes_estudo(r.id, "simula rascunho salvo sem limpar confirmação")
    assert repo.obter_rascunho(r.id).confirmacao_comparativo is not None
    assert client.get(f"/api/estudos/{r.id}/snapshot-aprovado").json()["estado"] == "superado"

    calc = client.post(f"/api/estudos/{r.id}/calcular")
    assert calc.status_code == 200
    body = calc.json()
    conf2 = client.post(
        f"/api/estudos/{r.id}/comparativo/confirmar",
        json={
            "hash_comparativo": body["hash_comparativo"],
            "opcao_ids": _ids_propostas(body),
        },
    )
    assert conf2.status_code == 200, conf2.text
    st = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert st.json()["estado"] == "candidato"
    assert comparativo_revisao_confirmada(repo.obter_rascunho(r.id))


def test_09_trocar_selecao_depois_de_confirmar_supera(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "t3.db")
    client = _client(repo)
    from tests.test_comparativo_multiplas_propostas import _rascunho_quatro_propostas

    r = _rascunho_quatro_propostas()
    r.id = "t3-sel"
    repo.salvar_rascunho(r)
    calc = client.post(f"/api/estudos/{r.id}/calcular")
    assert calc.status_code == 200
    hash_cmp = calc.json()["hash_comparativo"]
    conf = client.post(
        f"/api/estudos/{r.id}/comparativo/confirmar",
        json={"hash_comparativo": hash_cmp, "opcao_ids": ["op-1"]},
    )
    assert conf.status_code == 200, conf.text
    snap_id = conf.json()["snapshot_id"]
    put = client.put(
        f"/api/estudos/{r.id}/comparativo/selecao-apresentacao",
        json={"opcao_ids": ["op-1", "op-2"]},
    )
    assert put.status_code == 200
    snap = SnapshotRepository(tmp_path / "t3.db").obter_snapshot(snap_id)
    assert snap is not None
    assert snap.estado == "superado"
    salvo = repo.obter_rascunho(r.id)
    assert salvo is not None
    assert salvo.confirmacao_comparativo is None


def test_10_autoaprovacao_sem_justificativa_recusada(tmp_path: Path):
    repo, _, _, snap_svc, _, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-auto"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    with pytest.raises(AprovacaoInvalidaError, match="Justificativa"):
        snap_svc.aprovar_snapshot(
            r.id,
            gerado.snapshot_id,
            AprovarSnapshotRequest(
                revisor_nome="Ana",
                confirmo_conteudo=True,
                auto_aprovacao=True,
            ),
        )


def test_11_aprovar_que_nao_e_candidato_recusado(tmp_path: Path):
    repo, _, _, snap_svc, _, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-nao-cand"
    repo.salvar_rascunho(r)
    gerado = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    with pytest.raises(AprovacaoInvalidaError, match="candidatos"):
        snap_svc.aprovar_snapshot(
            r.id,
            gerado.snapshot_id,
            AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
        )


def test_duas_vivas_etapa5_exibe_e_exporta_uma(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, apres = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-duas"
    id_antiga, id_nova = _duas_aprovacoes_vivas(repo, snap_repo, snap_svc, r)
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2

    client = _client(repo)
    status = client.get(f"/api/estudos/{r.id}/snapshot-aprovado")
    assert status.status_code == 200
    body = status.json()
    assert body["aprovado"] is True
    assert body["estado"] == "aprovado"
    assert body["snapshot_id"] == id_nova
    assert body["aprovacao"]["revisor_nome"] == "Bruno"
    assert body["aprovacao"]["aprovado_em"]
    # GET só lê: as duas vivas permanecem até a migração 2.8.3.
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2

    res = apres.gerar_html(
        r.id,
        body["snapshot_id"],
        GerarApresentacaoRequest(modo="resumo", propostas_selecionadas=["op-1"]),
    )
    assert res.entregavel_id


def test_aprovar_segundo_nao_deixa_dois_em_vigor(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-supera"
    id_a, id_b = _duas_aprovacoes_vivas(repo, snap_repo, snap_svc, r)
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 2
    s_b = snap_svc.obter_snapshot(id_b)
    s3 = SnapshotCalculo(
        id=str(uuid.uuid4()),
        estudo_id=r.id,
        estado="candidato",
        hash_sha256=s_b.hash_sha256,
        payload=s_b.payload,
        compiler_versao=s_b.compiler_versao,
        motor_versao=s_b.motor_versao,
        policy_set_versao=s_b.policy_set_versao,
        snapshot_versao=s_b.snapshot_versao,
        tem_bloqueio=False,
        criado_em=datetime.now(timezone.utc),
    )
    snap_repo.salvar_snapshot(s3)
    snap_svc.aprovar_snapshot(
        r.id,
        s3.id,
        AprovarSnapshotRequest(revisor_nome="Carla", confirmo_conteudo=True),
    )
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 1
    vivo = snap_repo.snapshot_aprovado_atual(r.id)
    assert vivo is not None
    assert vivo.id == s3.id
    historico = snap_repo.listar_aprovacoes_estudo(r.id)
    assert len(historico) == 3
    invalidadas = [a for a in historico if a.invalidada_em is not None]
    assert len(invalidadas) == 2
    assert {id_a, id_b} == {a.snapshot_id for a in invalidadas}


def test_historico_guarda_aprovacoes_anteriores(tmp_path: Path):
    repo, _, snap_repo, snap_svc, _, _ = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    r.id = "t3-hist"
    repo.salvar_rascunho(r)
    g1 = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        g1.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    g2 = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        g2.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Bruno", confirmo_conteudo=True),
    )
    assert snap_repo.contar_aprovacoes_vivas(r.id) == 1
    vivo = snap_repo.snapshot_aprovado_atual(r.id)
    assert vivo is not None
    assert vivo.id == g2.snapshot_id
    historico = snap_repo.listar_aprovacoes_estudo(r.id)
    assert len(historico) == 2
    antiga = next(a for a in historico if a.snapshot_id == g1.snapshot_id)
    assert antiga.invalidada_em is not None
    assert antiga.revisor_nome == "Ana"
    assert snap_svc.obter_snapshot(g1.snapshot_id).estado == "superado"
