"""Testes do registrador de diagnóstico operacional."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.config.paths import caminho_diagnostico_jsonl
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.diagnostico import listar_eventos, registrar_evento
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.extracao_cotacao import ExtracaoCotacaoService


def test_registrar_e_listar_eventos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path))
    registrar_evento(
        estudo_id="est-1",
        etapa="calculo",
        evento="calculo_bloqueios",
        detalhe={"bloqueios": [{"codigo": "B-05", "mensagem": "teste"}]},
    )
    eventos = listar_eventos(limite=10)
    assert len(eventos) == 1
    assert eventos[0]["evento"] == "calculo_bloqueios"
    assert eventos[0]["estudo_id"] == "est-1"
    assert caminho_diagnostico_jsonl().is_file()


def test_api_diagnostico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path))
    registrar_evento(
        estudo_id="demo-12",
        etapa="cotacao_pdf",
        evento="extracao_zero_opcoes",
        detalhe={"template_id": "omint-ocr-v1", "alertas": ["PDF-OMINT-OCR"]},
    )
    app = create_app(seed_demos=False)
    client = TestClient(app)
    res = client.get("/api/diagnostico?limite=50")
    assert res.status_code == 200
    data = res.json()
    assert any(e["evento"] == "extracao_zero_opcoes" for e in data["eventos"])


def test_importacao_pdf_registra_diagnostico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path))
    repo = SQLiteStudyRepository(tmp_path / "e.db")
    cot_repo = ExtracaoCotacaoRepository(tmp_path / "c.db")
    svc = ExtracaoCotacaoService(
        repo,
        cot_repo,
        uploads_dir=tmp_path / "pdfs",
    )
    from newport_app.siscor_mapper.apply import rascunho_vazio

    repo.salvar_rascunho(rascunho_vazio("est-x", "Teste"))

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "OMINT")
    pdf_bytes = doc.tobytes()
    doc.close()

    monkeypatch.setattr(
        "newport_app.cotacao_pdf.ocr.tesseract_disponivel",
        lambda: False,
    )
    svc.importar_pdf("est-x", pdf_bytes, "omint.pdf")

    eventos = listar_eventos(limite=20)
    assert any(e["evento"] in ("extracao_pdf", "extracao_zero_opcoes") for e in eventos)


def test_extracao_zero_opcoes_omint_pendente(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "newport_app.cotacao_pdf.ocr.tesseract_disponivel",
        lambda: False,
    )
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "OMINT")
    conteudo = doc.tobytes()
    doc.close()
    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="t",
        documento_id="d-omint",
        nome_arquivo="omint.pdf",
    )
    assert ext.estado == "ocr_pendente"
    assert len([o for o in ext.opcoes if not o.excluida]) == 1
