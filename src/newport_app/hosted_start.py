"""Sobe a API na porta da plataforma ($PORT). Uso: python -m newport_app.hosted_start."""

from __future__ import annotations

import os

MENSAGEM_MODO_REAL = "hospedagem exige NEWPORT_MODO=real"


def exigir_ambiente_hospedado() -> None:
    """Trava de segurança: hosted só sobe em modo real com SUPABASE_URL."""
    hosted = (os.environ.get("NEWPORT_HOSTED") or "").strip().lower()
    if hosted not in {"1", "true", "yes", "sim"}:
        return
    modo = (os.environ.get("NEWPORT_MODO") or "").strip().lower()
    if modo != "real":
        raise RuntimeError(MENSAGEM_MODO_REAL)
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "NEWPORT_MODO=real e SUPABASE_URL não está definida. "
            "O backend não sobe sem autenticação. Defina SUPABASE_URL "
            "(o mesmo valor de VITE_SUPABASE_URL). Nunca use a chave "
            "service_role."
        )


def porta_http() -> int:
    bruto = (os.environ.get("PORT") or "8000").strip()
    try:
        porta = int(bruto)
    except ValueError as exc:
        raise RuntimeError(
            f"PORT inválida: {bruto!r}. A plataforma deve injetar um número."
        ) from exc
    if not 1 <= porta <= 65535:
        raise RuntimeError(f"PORT fora da faixa: {porta}.")
    return porta


def host_http() -> str:
    from newport_app.config.runtime import bind_host_configurado

    return bind_host_configurado()


def main() -> None:
    import uvicorn

    from newport_app.config.env import carregar_env_local
    from newport_app.config.logs import instalar_filtro_logs

    carregar_env_local()
    exigir_ambiente_hospedado()
    instalar_filtro_logs()
    uvicorn.run(
        "newport_app.api.main:app",
        host=host_http(),
        port=porta_http(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
