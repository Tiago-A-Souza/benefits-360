"""Sincronização automática de cenários (etapa 3/4) — um vs. múltiplos planos atuais."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import OpcaoPropostaRascunho
from newport_app.rascunho.cenarios_sync import (
    cenarios_sincronizados,
    sincronizar_cenarios,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.pendencias import pendencias_compilacao


def _rascunho_atef(n_opcoes: int = 4):
    """Estudo fictício tipo Atef: 1 plano atual, várias propostas."""
    base = rascunho_demo_12_vidas()
    opcoes: list[OpcaoPropostaRascunho] = []
    for i in range(n_opcoes):
        op = deepcopy(base.opcoes_proposta[0])
        op.id = f"op-{i + 1}"
        op.plano_nome = f"Proposta {i + 1}"
        op.extracao_id = f"ext-{i + 1}" if i % 2 == 0 else None
        opcoes.append(op)
    base.opcoes_proposta = opcoes
    base.cenarios = []
    return base


@pytest.fixture
def repo(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "cenarios.db")


@pytest.fixture
def client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def test_unico_plano_quatro_propostas_gera_quatro_cenarios(repo):
    rascunho = _rascunho_atef(4)
    repo.salvar_rascunho(rascunho)

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert len(salvo.cenarios) == 4
    assert cenarios_sincronizados(salvo)
    sg_id = salvo.subgrupos_atuais[0].id
    for op in salvo.opcoes_proposta:
        cenario = next(
            c
            for c in salvo.cenarios
            if any(a.opcao_plano_id == op.id for a in c.atribuicoes)
        )
        assert cenario.atribuicoes[0].alvo_id == sg_id


def test_remover_propostas_reduz_cenarios_e_preserva_ids(repo):
    rascunho = _rascunho_atef(4)
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    ids_antes = {
        op.id: next(
            c.id
            for c in salvo.cenarios
            if any(a.opcao_plano_id == op.id for a in c.atribuicoes)
        )
        for op in salvo.opcoes_proposta
    }

    salvo.opcoes_proposta = [op for op in salvo.opcoes_proposta if op.id in ("op-1", "op-3")]
    repo.salvar_rascunho(salvo)

    depois = repo.obter_rascunho(rascunho.id)
    assert depois is not None
    assert len(depois.opcoes_proposta) == 2
    assert len(depois.cenarios) == 2
    for op_id in ("op-1", "op-3"):
        cenario = next(
            c
            for c in depois.cenarios
            if any(a.opcao_plano_id == op_id for a in c.atribuicoes)
        )
        assert cenario.id == ids_antes[op_id]


def test_readicionar_propostas_sem_duplicar_cenarios(repo):
    rascunho = _rascunho_atef(4)
    repo.salvar_rascunho(rascunho)

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    salvo.opcoes_proposta = salvo.opcoes_proposta[:2]
    repo.salvar_rascunho(salvo)
    assert len(repo.obter_rascunho(rascunho.id).cenarios) == 2

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    salvo.opcoes_proposta = _rascunho_atef(4).opcoes_proposta
    repo.salvar_rascunho(salvo)

    final = repo.obter_rascunho(rascunho.id)
    assert final is not None
    assert len(final.opcoes_proposta) == 4
    assert len(final.cenarios) == 4
    ids_cenarios = [c.id for c in final.cenarios]
    assert len(ids_cenarios) == len(set(ids_cenarios))


def test_proposta_manual_sincroniza_igual_pdf(repo):
    rascunho = _rascunho_atef(1)
    rascunho.opcoes_proposta[0].extracao_id = None
    repo.salvar_rascunho(rascunho)

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert len(salvo.cenarios) == 1
    assert cenarios_sincronizados(salvo)


def test_anistia_dois_planos_nao_associa_automaticamente(repo):
    rascunho = _rascunho_atef(2)
    sg2 = deepcopy(rascunho.subgrupos_atuais[0])
    sg2.id = "sg-2"
    sg2.plano_nome = "Plano atual B"
    rascunho.subgrupos_atuais.append(sg2)
    for i, vida in enumerate(rascunho.vidas):
        if i >= len(rascunho.vidas) // 2:
            vida.subgrupo_atual_id = "sg-2"
    rascunho.cenarios = []

    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert not cenarios_sincronizados(salvo)
    assert any(p.codigo == "APP-ET4-001" for p in pendencias_compilacao(salvo))


def test_anistia_correspondencia_manual_desbloqueia(repo):
    rascunho = _rascunho_atef(2)
    sg2 = deepcopy(rascunho.subgrupos_atuais[0])
    sg2.id = "sg-2"
    sg2.plano_nome = "Plano atual B"
    rascunho.subgrupos_atuais.append(sg2)
    rascunho.cenarios = [
        deepcopy(rascunho_demo_12_vidas().cenarios[0]).model_copy(
            update={
                "id": "c1",
                "atribuicoes": [
                    deepcopy(rascunho_demo_12_vidas().cenarios[0].atribuicoes[0]).model_copy(
                        update={"opcao_plano_id": "op-1", "alvo_id": "sg-1"}
                    )
                ],
            }
        ),
        deepcopy(rascunho_demo_12_vidas().cenarios[0]).model_copy(
            update={
                "id": "c2",
                "atribuicoes": [
                    deepcopy(rascunho_demo_12_vidas().cenarios[0].atribuicoes[0]).model_copy(
                        update={"id": "a2", "opcao_plano_id": "op-2", "alvo_id": "sg-2"}
                    )
                ],
            }
        ),
    ]
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert cenarios_sincronizados(salvo)
    assert not any(p.codigo == "APP-ET4-001" for p in pendencias_compilacao(salvo))


def test_get_rascunho_sincroniza_em_memoria_sem_persistir_orfaos(repo):
    rascunho = _rascunho_atef(2)
    repo.salvar_rascunho(rascunho)

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    salvo.opcoes_proposta = salvo.opcoes_proposta[:1]
    repo.salvar_rascunho(salvo)

    lido = repo.obter_rascunho(rascunho.id)
    assert lido is not None
    assert len(lido.cenarios) == 1


def test_api_unico_plano_pendencias_liberam_calculo(client: TestClient, repo):
    rascunho = _rascunho_atef(4)
    rascunho.id = "atef-sync"
    repo.salvar_rascunho(rascunho)

    res = client.get(f"/api/estudos/{rascunho.id}/rascunho")
    assert res.status_code == 200
    body = res.json()
    assert len(body["cenarios"]) == 4

    pend = client.get(f"/api/estudos/{rascunho.id}/pendencias").json()
    assert not any(p["codigo"] == "APP-ET4-001" for p in pend)


def test_sincronizar_cenarios_idempotente():
    rascunho = _rascunho_atef(3)
    sincronizar_cenarios(rascunho)
    ids1 = [c.id for c in rascunho.cenarios]
    sincronizar_cenarios(rascunho)
    ids2 = [c.id for c in rascunho.cenarios]
    assert ids1 == ids2
