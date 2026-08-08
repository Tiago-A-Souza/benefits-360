"""Seleção de planos em cotações PDF — multi-extração e erros legíveis."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.diagnostico import listar_eventos
from tests.fixtures.cotacao_pdf.build_pdfs import build_porto_27_paginas, build_sulamerica_sem_copart


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path))
    return TestClient(create_app(seed_demos=True), raise_server_exceptions=False)


def _importar(client: TestClient, estudo_id: str, nome: str, pdf: bytes) -> str:
    res = client.post(
        f"/api/estudos/{estudo_id}/importar-cotacao-pdf",
        files={"arquivo": (nome, pdf, "application/pdf")},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["opcoes_encontradas"] >= 1
    return data["extracao_id"]


def _primeira_opcao(client: TestClient, estudo_id: str, extracao_id: str) -> str:
    det = client.get(f"/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}")
    assert det.status_code == 200
    ops = [o for o in det.json()["opcoes"] if not o.get("excluida")]
    assert ops
    return ops[0]["id"]


def _selecionar(client: TestClient, estudo_id: str, extracao_id: str, opcao_id: str, sel: bool):
    return client.post(
        f"/api/estudos/{estudo_id}/extracao-cotacao/{extracao_id}/opcoes/{opcao_id}/selecionar",
        json={"selecionada": sel},
    )


def test_selecionar_tres_extracoes_e_toggle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    estudo = "demo-12"
    e1 = _importar(client, estudo, "porto.pdf", build_porto_27_paginas())
    e2 = _importar(client, estudo, "sul-a.pdf", build_sulamerica_sem_copart())
    e3 = _importar(client, estudo, "sul-b.pdf", build_sulamerica_sem_copart())

    for eid in (e1, e2, e3):
        oid = _primeira_opcao(client, estudo, eid)
        r1 = _selecionar(client, estudo, eid, oid, True)
        assert r1.status_code == 200, r1.text
        assert r1.json()["opcao"]["selecionada_para_comparativo"] is True
        r2 = _selecionar(client, estudo, eid, oid, False)
        assert r2.status_code == 200, r2.text
        assert r2.json()["opcao"]["selecionada_para_comparativo"] is False
        r3 = _selecionar(client, estudo, eid, oid, True)
        assert r3.status_code == 200, r3.text
        assert r3.json()["opcao"]["selecionada_para_comparativo"] is True

    lista = client.get(f"/api/estudos/{estudo}/extracao-cotacao")
    assert lista.status_code == 200
    selecionadas = sum(
        1
        for ex in lista.json().get("extracoes", [])
        for op in ex.get("opcoes", [])
        if op.get("selecionada_para_comparativo")
    )
    assert selecionadas == 3


def test_selecionar_opcao_inexistente_retorna_404_legivel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    client = _client(tmp_path, monkeypatch)
    estudo = "demo-12"
    eid = _importar(client, estudo, "porto.pdf", build_porto_27_paginas())
    res = _selecionar(client, estudo, eid, "opcao-inexistente-xyz", True)
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["codigo"] == "PDF-SEL-002"
    assert "não encontrado" in detail["mensagem"].lower()
    eventos = listar_eventos(limite=50)
    assert any(e["evento"] == "selecao_opcao_falhou" for e in eventos)


def test_selecionar_extracao_removida_erro_claro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    client = _client(tmp_path, monkeypatch)
    estudo = "demo-12"
    eid = _importar(client, estudo, "porto.pdf", build_porto_27_paginas())
    oid = _primeira_opcao(client, estudo, eid)
    rem = client.delete(f"/api/estudos/{estudo}/extracao-cotacao/{eid}")
    assert rem.status_code == 200, rem.text
    res = _selecionar(client, estudo, eid, oid, True)
    assert res.status_code == 404
    detail = res.json()["detail"]
    assert detail["codigo"] == "PDF-SEL-001"
    assert "removid" in detail["mensagem"].lower() or "não encontrada" in detail["mensagem"].lower()


@pytest.mark.private_corpus
def test_selecao_atef_porto_e_duas_sulamerica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    atef = Path(r"C:\Users\tiago\Downloads\ATEF-20260807T152847Z-1-001\ATEF")
    porto = next(Path(".private/corpus").rglob("PORTO3.pdf"), None)
    if porto is None or not atef.is_dir():
        pytest.skip("Corpus ATEF/Porto3 indisponível")
    sul = next(atef.rglob("SULAMERICA.pdf"), None)
    sul_sem = next(atef.rglob("SULAMERICA SEM CP.pdf"), None)
    if not sul or not sul_sem:
        pytest.skip("PDFs SulAmérica ATEF indisponíveis")

    client = _client(tmp_path, monkeypatch)
    estudo = "demo-12"
    ids = []
    for path in (porto, sul, sul_sem):
        ids.append(_importar(client, estudo, path.name, path.read_bytes()))
    for eid in ids:
        oid = _primeira_opcao(client, estudo, eid)
        res = _selecionar(client, estudo, eid, oid, True)
        assert res.status_code == 200, res.text
