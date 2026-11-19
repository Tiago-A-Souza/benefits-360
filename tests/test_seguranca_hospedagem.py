"""Cabeçalhos, JWT em /api, limite de upload e logs sem segredo."""

from __future__ import annotations

import logging
import re

from fastapi.testclient import TestClient

from newport_app.config.logs import redigir_segredos
from newport_app.diagnostico import registrar_evento, listar_eventos
from tests.test_etapa_3b import _app_real, _token


def test_cabecalhos_seguranca_em_saude(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    monkeypatch.setenv("NEWPORT_VOLUME_DIR", str(tmp_path / "vol"))
    client = TestClient(_app_real(tmp_path, monkeypatch))
    res = client.get("/api/saude")
    assert res.status_code == 200
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("referrer-policy") == "no-referrer"
    assert "default-src 'self'" in res.headers.get("content-security-policy", "")
    assert "max-age=" in (res.headers.get("strict-transport-security") or "")


def test_rotas_api_exigem_jwt_exceto_saude(tmp_path, monkeypatch):
    client = TestClient(_app_real(tmp_path, monkeypatch))
    publicas = {"/api/saude"}
    falhas = []
    for route in client.app.routes:
        path = getattr(route, "path", "") or ""
        if not path.startswith("/api/") or path in publicas:
            continue
        metodos = getattr(route, "methods", None) or {"GET"}
        url = re.sub(r"\{[^}]+\}", "x", path)
        for metodo in metodos:
            if metodo in {"HEAD", "OPTIONS"}:
                continue
            res = client.request(metodo, url)
            if res.status_code != 401:
                falhas.append((metodo, path, res.status_code))
    assert falhas == []


def test_content_length_acima_do_limite_413(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWPORT_UPLOAD_MAX_BYTES", "64")
    client = TestClient(_app_real(tmp_path, monkeypatch))
    res = client.post(
        "/api/estudos",
        content=b"x" * 80,
        headers={
            "Authorization": f"Bearer {_token('user-a')}",
            "Content-Type": "application/json",
        },
    )
    assert res.status_code == 413


def test_diagnostico_nao_grava_cpf_nem_token(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path / "demo"))
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(tmp_path / "priv"))
    registrar_evento(
        estudo_id="est-x",
        etapa="teste",
        evento="probe",
        detalhe={"cpf": "11144477735", "token": "eyJhbGciOiJIUzI1NiJ9.aaa", "ok": 1},
    )
    ev = listar_eventos(limite=5)[-1]
    texto = str(ev)
    assert "11144477735" not in texto
    assert "cpf" not in ev["detalhe"]
    assert "token" not in ev["detalhe"]
    assert ev["detalhe"]["ok"] == 1


def test_logs_redigem_bearer_e_jwt():
    bruto = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaa.bbb"
    limpo = redigir_segredos(bruto)
    assert "eyJ" not in limpo
    assert "[redacted]" in limpo or "[jwt-redacted]" in limpo
    rec = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, bruto, (), None
    )
    from newport_app.config.logs import SemSegredoFilter

    assert SemSegredoFilter().filter(rec) is True
    assert "eyJ" not in str(rec.msg)
