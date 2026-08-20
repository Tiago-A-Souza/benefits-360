"""Confirmação persistida do comparativo — desbloqueio da etapa Apresentação."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import OpcaoPropostaRascunho
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import comparativo_revisao_confirmada


def _rascunho_pronto():
    base = rascunho_demo_12_vidas()
    sincronizar_cenarios(base)
    return base


@pytest.fixture
def repo(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "confirm.db")


@pytest.fixture
def client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def _calcular_hash(client: TestClient, estudo_id: str) -> str:
    res = client.post(f"/api/estudos/{estudo_id}/calcular")
    assert res.status_code == 200
    body = res.json()
    assert body["calculo_realizado"] is True
    assert body["hash_comparativo"]
    return body["hash_comparativo"]


def test_calcular_sem_confirmar_nao_libera_comparativo(client: TestClient, repo):
    rascunho = _rascunho_pronto()
    rascunho.id = "atef-confirm"
    repo.salvar_rascunho(rascunho)

    _calcular_hash(client, rascunho.id)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert not comparativo_revisao_confirmada(salvo)


def test_confirmar_libera_e_persiste(client: TestClient, repo):
    rascunho = _rascunho_pronto()
    rascunho.id = "atef-ok"
    repo.salvar_rascunho(rascunho)

    hash_cmp = _calcular_hash(client, rascunho.id)
    res = client.post(
        f"/api/estudos/{rascunho.id}/comparativo/confirmar",
        json={"hash_comparativo": hash_cmp, "opcao_ids": ["op-1"]},
    )
    assert res.status_code == 200

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert comparativo_revisao_confirmada(salvo)
    assert salvo.confirmacao_comparativo.ordem == ["op-1"]
    assert salvo.selecao_apresentacao.ordem == ["op-1"]


def test_recarregar_mantem_confirmacao(client: TestClient, repo):
    rascunho = _rascunho_pronto()
    rascunho.id = "reload-confirm"
    repo.salvar_rascunho(rascunho)
    hash_cmp = _calcular_hash(client, rascunho.id)
    client.post(
        f"/api/estudos/{rascunho.id}/comparativo/confirmar",
        json={"hash_comparativo": hash_cmp, "opcao_ids": ["op-1"]},
    )

    res = client.get(f"/api/estudos/{rascunho.id}/rascunho")
    assert res.status_code == 200
    body = res.json()
    assert body["confirmacao_comparativo"]["ordem"] == ["op-1"]


def test_alterar_proposta_invalida_confirmacao(client: TestClient, repo):
    rascunho = _rascunho_pronto()
    rascunho.id = "inv-prop"
    repo.salvar_rascunho(rascunho)
    hash_cmp = _calcular_hash(client, rascunho.id)
    client.post(
        f"/api/estudos/{rascunho.id}/comparativo/confirmar",
        json={"hash_comparativo": hash_cmp, "opcao_ids": ["op-1"]},
    )

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    salvo.opcoes_proposta[0].plano_nome = "Proposta alterada"
    repo.salvar_rascunho(salvo)

    depois = repo.obter_rascunho(rascunho.id)
    assert depois is not None
    assert depois.confirmacao_comparativo is None


def test_passos_visiveis_um_plano():
    """Com 1 plano atual: Comparativo é a 4ª e última etapa."""
    rascunho = _rascunho_pronto()
    assert len(rascunho.subgrupos_atuais) == 1
    chaves = ["base", "plano", "cotacoes", "comparativo"]
    assert len(chaves) == 4
    assert chaves.index("comparativo") == 3
    assert "apresentacao" not in chaves


def test_passos_visiveis_dois_planos():
    """Com 2+ planos atuais: Correspondência=4, Comparativo=5 — sem etapa 6."""
    rascunho = _rascunho_pronto()
    sg2 = deepcopy(rascunho.subgrupos_atuais[0])
    sg2.id = "sg-2"
    rascunho.subgrupos_atuais.append(sg2)
    chaves = ["base", "plano", "cotacoes", "selecionados", "comparativo"]
    assert len(chaves) == 5
    assert chaves.index("selecionados") == 3
    assert chaves.index("comparativo") == 4
    assert "apresentacao" not in chaves


def test_confirmar_exige_selecao(client: TestClient, repo):
    rascunho = _rascunho_pronto()
    rascunho.id = "sem-sel"
    repo.salvar_rascunho(rascunho)
    hash_cmp = _calcular_hash(client, rascunho.id)
    res = client.post(
        f"/api/estudos/{rascunho.id}/comparativo/confirmar",
        json={"hash_comparativo": hash_cmp, "opcao_ids": []},
    )
    assert res.status_code == 422
