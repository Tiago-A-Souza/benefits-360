"""Start hospedado: $PORT e bind público só com NEWPORT_HOSTED."""

from __future__ import annotations

from pathlib import Path

from newport_app.config.runtime import bind_host_configurado, exigir_host_local_modo_real
from newport_app.hosted_start import (
    exigir_ambiente_hospedado,
    host_http,
    porta_http,
)


def test_porta_padrao_e_env(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert porta_http() == 8000
    monkeypatch.setenv("PORT", "8088")
    assert porta_http() == 8088


def test_porta_invalida(monkeypatch):
    import pytest

    monkeypatch.setenv("PORT", "abc")
    with pytest.raises(RuntimeError, match="PORT inválida"):
        porta_http()


def test_bind_com_port_exige_hosted_no_modo_real(monkeypatch):
    import pytest

    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.delenv("NEWPORT_HOSTED", raising=False)
    monkeypatch.delenv("NEWPORT_BIND_HOST", raising=False)
    monkeypatch.setenv("PORT", "8080")
    assert bind_host_configurado() == "0.0.0.0"
    with pytest.raises(RuntimeError, match="NEWPORT_HOSTED"):
        exigir_host_local_modo_real()
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    exigir_host_local_modo_real()
    assert host_http() == "0.0.0.0"


def test_hosted_start_recusa_modo_nao_real(monkeypatch):
    import pytest

    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    monkeypatch.setenv("SUPABASE_URL", "https://exemplo.supabase.co")
    with pytest.raises(RuntimeError, match="hospedagem exige NEWPORT_MODO=real"):
        exigir_ambiente_hospedado()
    monkeypatch.delenv("NEWPORT_MODO", raising=False)
    with pytest.raises(RuntimeError, match="hospedagem exige NEWPORT_MODO=real"):
        exigir_ambiente_hospedado()


def test_hosted_start_recusa_sem_supabase_url(monkeypatch):
    import pytest

    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        exigir_ambiente_hospedado()


def test_hosted_start_aceita_real_com_supabase(monkeypatch):
    monkeypatch.setenv("NEWPORT_HOSTED", "1")
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("SUPABASE_URL", "https://exemplo.supabase.co")
    exigir_ambiente_hospedado()


def test_dockerfile_saude_e_port():
    texto = Path("Dockerfile").read_text(encoding="utf-8")
    assert "PORT" in texto
    assert "/api/saude" in texto
    assert "newport_app.hosted_start" in texto
    assert "HEALTHCHECK" in texto


def test_guia_hospedagem_existe():
    texto = Path("docs/HOSPEDAGEM.md").read_text(encoding="utf-8")
    for trecho in (
        "Railway",
        "/data",
        "NEWPORT_HOSTED",
        "hospedagem exige NEWPORT_MODO=real",
        "VITE_SUPABASE_ANON_KEY",
        "service_role",
        "python -m newport_app.backup",
        "Rollback",
        "acesso à rede local",
    ):
        assert trecho in texto, trecho
