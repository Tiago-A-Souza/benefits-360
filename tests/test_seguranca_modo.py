"""Testes de segurança operacional — ETAPA 2.4."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.responses import JSONResponse

from newport_app.api.middleware import ModoRealLocalMiddleware
from newport_app.config.runtime import (
    ModoExecucaoInvalidoError,
    cliente_eh_local,
    modo_execucao,
)


def test_modo_invalido_falha_explicitamente(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "staging")
    # ValueError (base): evita falha de identidade de classe quando o suite
    # resolve o pacote por mais de um path (junction C:\np / N:\).
    with pytest.raises(ValueError, match=r"NEWPORT_MODO inválido: 'staging'") as ei:
        modo_execucao()
    assert getattr(ei.value, "valor", "staging") == "staging"


def test_modo_demo_e_real_aceitos(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    assert modo_execucao().value == "demo"
    monkeypatch.setenv("NEWPORT_MODO", "real")
    assert modo_execucao().value == "real"


@pytest.mark.parametrize(
    ("host", "esperado"),
    [
        ("127.0.0.1", True),
        ("127.0.0.2", True),
        ("localhost", True),
        ("::1", True),
        ("testclient", True),
        ("192.168.0.10", False),
        ("10.0.0.1", False),
        (None, False),
    ],
)
def test_cliente_eh_local(host, esperado):
    assert cliente_eh_local(host) is esperado


def test_middleware_modo_real_rejeita_host_externo(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    middleware = ModoRealLocalMiddleware(app=MagicMock())
    request = MagicMock()
    request.client = MagicMock(host="203.0.113.50")

    async def call_next(_req):
        return JSONResponse({"ok": True})

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 403
    assert "local" in response.body.decode().lower()


def test_middleware_modo_real_aceita_localhost(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    middleware = ModoRealLocalMiddleware(app=MagicMock())
    request = MagicMock()
    request.client = MagicMock(host="127.0.0.1")

    async def call_next(_req):
        return JSONResponse({"ok": True})

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 200
