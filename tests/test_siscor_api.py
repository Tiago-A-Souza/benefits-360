"""Testes de integração — API importação SISCOR (ETAPA 2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
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


def _importar(client: TestClient, estudo_id: str, xlsx: bytes, **params):
    files = {
        "arquivo": (
            "planilha.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    return client.post(f"/api/estudos/{estudo_id}/importar-siscor", files=files, params=params)


def test_criar_estudo_vazio_e_importar(client: TestClient):
    res = client.post(
        "/api/estudos",
        json={"id": "cli-12", "titulo": "Cliente 12 vidas", "nome_empresa": "Cliente Teste"},
    )
    assert res.status_code == 200
    imp = _importar(client, "cli-12", planilha_12_vidas(), titulo="Cliente 12 vidas")
    assert imp.status_code == 200
    data = imp.json()
    assert data["sucesso"] is True
    assert data["resumo"]["estatisticas"]["total_linhas_lidas"] == 12
    assert data["resumo"]["estatisticas"]["confirmadas"] == 0


def test_importar_41_vidas_dois_planos(client: TestClient):
    client.post("/api/estudos", json={"id": "cli-41", "titulo": "41 vidas", "nome_empresa": "Empresa 41"})
    imp = _importar(client, "cli-41", planilha_41_vidas_2_planos())
    assert imp.status_code == 200
    stats = imp.json()["resumo"]["estatisticas"]
    assert stats["total_linhas_lidas"] == 41
    assert stats["planos_detectados"] == 2


def test_conferencia_lista_linhas(client: TestClient):
    client.post("/api/estudos", json={"id": "conf", "titulo": "Conf", "nome_empresa": "Conf"})
    _importar(client, "conf", planilha_12_vidas())
    res = client.get("/api/estudos/conf/conferencia-siscor")
    assert res.status_code == 200
    body = res.json()
    assert len(body["linhas"]) == 12
    assert body["estatisticas"]["confirmadas"] == 0


def test_reimportacao_retorna_409(client: TestClient):
    client.post("/api/estudos", json={"id": "409", "titulo": "409", "nome_empresa": "409"})
    _importar(client, "409", planilha_12_vidas())
    segunda = _importar(client, "409", planilha_12_vidas())
    assert segunda.status_code == 409
    assert "opcoes" in segunda.json()["detail"]


def test_reimportacao_substituir(client: TestClient):
    client.post("/api/estudos", json={"id": "sub", "titulo": "Sub", "nome_empresa": "Sub"})
    _importar(client, "sub", planilha_12_vidas())
    segunda = _importar(client, "sub", planilha_12_vidas(), modo="substituir")
    assert segunda.status_code == 200
    assert segunda.json()["resumo"]["versao"] == 2


def test_confirmar_lote(client: TestClient):
    client.post("/api/estudos", json={"id": "lote", "titulo": "Lote", "nome_empresa": "Lote"})
    _importar(client, "lote", planilha_12_vidas())
    res = client.post("/api/estudos/lote/conferencia-siscor/confirmar-lote")
    assert res.status_code == 200
    assert res.json()["confirmadas"] == 12
    assert res.json()["vidas_no_rascunho"] == 12


def test_pos_siscor_calcular_bloqueia_tipo_fiscal(client: TestClient):
    client.post("/api/estudos", json={"id": "calc", "titulo": "Calc", "nome_empresa": "Calc"})
    _importar(client, "calc", planilha_12_vidas())
    client.post("/api/estudos/calc/conferencia-siscor/confirmar-lote")
    res = client.post("/api/estudos/calc/calcular")
    assert res.status_code == 422
    erros = res.json()["detail"]["erros"]
    codigos = {e["codigo"] for e in erros}
    assert "APP-IMP-001" in codigos or "APP-IMP-002" in codigos


def test_erro_arquivo_nao_expoe_conteudo_linha(client: TestClient):
    client.post("/api/estudos", json={"id": "err", "titulo": "Err", "nome_empresa": "Err"})
    files = {"arquivo": ("bad.txt", b"conteudo ficticio", "text/plain")}
    res = client.post("/api/estudos/err/importar-siscor", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["sucesso"] is False
    texto = res.text
    assert "Beneficiário Fictício" not in texto
    assert "conteudo ficticio" not in texto


def test_atualizar_linha_reseta_confirmacao(client: TestClient):
    client.post("/api/estudos", json={"id": "patch", "titulo": "Patch", "nome_empresa": "Patch"})
    _importar(client, "patch", planilha_12_vidas())
    conf = client.get("/api/estudos/patch/conferencia-siscor").json()
    linha_id = conf["linhas"][0]["id"]
    client.post("/api/estudos/patch/conferencia-siscor/confirmar-lote")
    res = client.patch(
        f"/api/estudos/patch/conferencia-siscor/linhas/{linha_id}",
        json={"segurado": "Beneficiário Corrigido Fictício"},
    )
    assert res.status_code == 200
    assert res.json()["linha"]["registro_confirmado"] is False
