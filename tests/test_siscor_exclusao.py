"""Exclusão e reversão de vidas na conferência SISCOR."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    PriceBasisRascunho,
    RegimeCopartRascunho,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_app.services.importacao_siscor import ImportacaoSiscorService
from tests.fixtures.siscor.xlsx_builder import planilha_12_vidas, planilha_41_vidas_2_planos


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "test.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    app = create_app(
        repo=repo,
        import_repo=imp,
        uploads_dir=tmp_path / "uploads",
        seed_demos=False,
    )
    return TestClient(app)


@pytest.fixture
def servico(tmp_path: Path) -> ImportacaoSiscorService:
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    return ImportacaoSiscorService(repo, imp, uploads_dir=tmp_path / "uploads")


def _importar(client: TestClient, estudo_id: str, xlsx: bytes, **params):
    files = {
        "arquivo": (
            "planilha.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    return client.post(f"/api/estudos/{estudo_id}/importar-siscor", files=files, params=params)


def _setup_estudo_12(client: TestClient) -> str:
    estudo_id = "exc-12"
    client.post(
        "/api/estudos",
        json={"id": estudo_id, "titulo": "Exclusão 12", "nome_empresa": "Exclusão"},
    )
    _importar(client, estudo_id, planilha_12_vidas())
    return estudo_id


def _enriquecer_rascunho_pos_siscor(rascunho):
    demo = rascunho_demo_12_vidas()
    rascunho.regimes_copart = [RegimeCopartRascunho(id="regime-sem", tipo="sem")]
    for sg in rascunho.subgrupos_atuais:
        sg.tipo_fiscal = "seguradora"
        sg.regime_copart_id = "regime-sem"
        sg.fatura_price_basis = PriceBasisRascunho.EXCLUI_IOF
    for vida in rascunho.vidas:
        if vida.valor_fatura:
            vida.valor_fatura.price_basis = PriceBasisRascunho.EXCLUI_IOF
    opcoes: list[OpcaoPropostaRascunho] = []
    for i in range(2):
        op = deepcopy(demo.opcoes_proposta[0])
        op.id = f"op-{i + 1}"
        op.plano_nome = f"Proposta {i + 1}"
        opcoes.append(op)
    rascunho.opcoes_proposta = opcoes
    sincronizar_cenarios(rascunho)
    rascunho.escolhas = EscolhasEstudo(
        data_referencia_idade=date(2026, 6, 30),
        baseline_escolhido=CampoConfirmavelBaseline(valor="reajustado", confirmado=True),
        precedencia_atual_vida=CampoConfirmavelPrecedencia(
            valor="tabela_atual", confirmado=True
        ),
    )
    return rascunho


def test_excluir_sem_motivo_retorna_400(client: TestClient):
    estudo_id = _setup_estudo_12(client)
    conf = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    linha_id = conf["linhas"][0]["id"]
    res = client.patch(
        f"/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}",
        json={"excluida": True},
    )
    assert res.status_code == 400
    assert "motivo" in res.json()["detail"].lower()


def test_excluir_com_motivo_atualiza_contadores(client: TestClient):
    estudo_id = _setup_estudo_12(client)
    conf = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    stats_antes = conf["estatisticas"]
    assert stats_antes["total_linhas_lidas"] == 12
    assert stats_antes["qtd_excluidas"] == 0

    linha = conf["linhas"][0]
    res = client.patch(
        f"/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha['id']}",
        json={"excluida": True, "motivo_exclusao": "Beneficiário desligado da empresa."},
    )
    assert res.status_code == 200
    body = res.json()["linha"]
    assert body["excluida"] is True
    assert body["motivo_exclusao"] == "Beneficiário desligado da empresa."

    conf2 = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    stats = conf2["estatisticas"]
    assert stats["total_linhas_lidas"] == 11
    assert stats["qtd_excluidas"] == 1
    assert (
        stats["qtd_titulares"] + stats["qtd_dependentes"] + stats["qtd_sem_parentesco"]
        == stats["total_linhas_lidas"]
    )


def test_reverter_exclusao_restaura_contadores(client: TestClient):
    estudo_id = _setup_estudo_12(client)
    conf = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    linha_id = conf["linhas"][0]["id"]
    client.patch(
        f"/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}",
        json={"excluida": True, "motivo_exclusao": "Teste reversão."},
    )
    res = client.patch(
        f"/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}",
        json={"excluida": False},
    )
    assert res.status_code == 200
    assert res.json()["linha"]["excluida"] is False
    assert res.json()["linha"]["motivo_exclusao"] is None

    conf2 = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    stats = conf2["estatisticas"]
    assert stats["total_linhas_lidas"] == 12
    assert stats["qtd_excluidas"] == 0


def test_excluir_todas_vidas_subgrupo_nao_gera_b06(servico: ImportacaoSiscorService):
    estudo_id = "exc-41"
    servico.importar_planilha(estudo_id, planilha_41_vidas_2_planos(), titulo="41 vidas")
    candidata = servico._importacoes.obter_ativa(estudo_id)
    assert candidata is not None
    plano_b = "Plano Fictício B"
    for linha in candidata.linhas:
        if linha.plano == plano_b:
            servico.atualizar_linha(
                estudo_id,
                linha.id,
                excluida=True,
                motivo_exclusao="Plano encerrado.",
            )

    servico.confirmar_lote(estudo_id)
    rascunho = servico._estudos.obter_rascunho(estudo_id)
    assert rascunho is not None
    assert len(rascunho.vidas) == 36
    assert len(rascunho.subgrupos_atuais) == 1

    rascunho = _enriquecer_rascunho_pos_siscor(rascunho)
    servico._estudos.salvar_rascunho(rascunho)

    resp = CalculoService(servico._estudos).calcular(estudo_id)
    assert not any(b.codigo == "B-06" for b in resp.consistencia.bloqueios)


def test_salvar_nome_vazio_registra_app_sis_007(client: TestClient):
    estudo_id = _setup_estudo_12(client)
    conf = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    linha_id = conf["linhas"][0]["id"]
    res = client.patch(
        f"/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}",
        json={"segurado": ""},
    )
    assert res.status_code == 200
    codigos = {a["codigo"] for a in res.json()["linha"]["alertas"]}
    assert "APP-SIS-007" in codigos


def test_salvar_edicao_valida_sem_regressao(client: TestClient):
    estudo_id = _setup_estudo_12(client)
    conf = client.get(f"/api/estudos/{estudo_id}/conferencia-siscor").json()
    linha_id = conf["linhas"][0]["id"]
    client.post(f"/api/estudos/{estudo_id}/conferencia-siscor/confirmar-lote")
    res = client.patch(
        f"/api/estudos/{estudo_id}/conferencia-siscor/linhas/{linha_id}",
        json={"segurado": "Beneficiário Corrigido Fictício"},
    )
    assert res.status_code == 200
    linha = res.json()["linha"]
    assert linha["segurado"] == "Beneficiário Corrigido Fictício"
    assert linha["registro_confirmado"] is False
    assert not linha["excluida"]
    assert not any(a["codigo"] == "APP-SIS-007" for a in linha["alertas"])
