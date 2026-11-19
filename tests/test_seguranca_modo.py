"""Testes de segurança operacional — ETAPA 2.4."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.responses import JSONResponse

from newport_app.api.middleware import ModoRealLocalMiddleware
from newport_app.auth.startup import (
    AuthNaoConfiguradaError,
    HospedagemNaoConfiguradaError,
    exigir_auth_configurada,
)
from newport_app.config.runtime import (
    cliente_eh_local,
    exigir_host_local_modo_real,
    modo_execucao,
    modo_hospedado,
    origens_cors,
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
    monkeypatch.delenv("NEWPORT_HOSTED", raising=False)
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
    monkeypatch.delenv("NEWPORT_HOSTED", raising=False)
    middleware = ModoRealLocalMiddleware(app=MagicMock())
    request = MagicMock()
    request.client = MagicMock(host="127.0.0.1")

    async def call_next(_req):
        return JSONResponse({"ok": True})

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 200


def test_middleware_hospedado_aceita_host_externo(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    middleware = ModoRealLocalMiddleware(app=MagicMock())
    request = MagicMock()
    request.client = MagicMock(host="203.0.113.50")

    async def call_next(_req):
        return JSONResponse({"ok": True})

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 200


def test_bind_publico_so_com_hosted(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.delenv("NEWPORT_HOSTED", raising=False)
    monkeypatch.setenv("NEWPORT_BIND_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="NEWPORT_HOSTED"):
        exigir_host_local_modo_real()
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    exigir_host_local_modo_real()


def test_hosted_recusa_demo(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    with pytest.raises(HospedagemNaoConfiguradaError, match="NEWPORT_MODO=real"):
        exigir_auth_configurada()


def test_hosted_recusa_sem_volume(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.delenv("NEWPORT_VOLUME_DIR", raising=False)
    monkeypatch.delenv("NEWPORT_PRIVATE_RUNTIME", raising=False)
    with pytest.raises(HospedagemNaoConfiguradaError, match="NEWPORT_VOLUME_DIR"):
        exigir_auth_configurada()


def test_hosted_sobe_com_essencial(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://exemplo.supabase.co")
    monkeypatch.setenv("NEWPORT_VOLUME_DIR", "/data")
    monkeypatch.setenv("NEWPORT_BIND_HOST", "0.0.0.0")
    exigir_auth_configurada()
    assert modo_hospedado() is True


def test_real_sem_supabase_ainda_recusa(monkeypatch):
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.delenv("NEWPORT_HOSTED", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "")
    with pytest.raises(AuthNaoConfiguradaError, match="SUPABASE_URL"):
        exigir_auth_configurada()


def test_origens_cors_aceitam_extra(monkeypatch):
    monkeypatch.delenv("NEWPORT_CORS_ORIGENS", raising=False)
    assert "http://localhost:5173" in origens_cors()
    monkeypatch.setenv("NEWPORT_CORS_ORIGENS", "https://piloto.exemplo, https://outro.exemplo/")
    origens = origens_cors()
    assert "https://piloto.exemplo" in origens
    assert "https://outro.exemplo" in origens
