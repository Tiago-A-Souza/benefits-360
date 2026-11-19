"""Sobe a API na porta da plataforma ($PORT). Uso: python -m newport_app.hosted_start."""

from __future__ import annotations

import os


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

    uvicorn.run(
        "newport_app.api.main:app",
        host=host_http(),
        port=porta_http(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
