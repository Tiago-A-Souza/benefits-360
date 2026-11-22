"""Modo de execução e limites operacionais."""

from __future__ import annotations

import os
from enum import Enum

_LIMITE_UPLOAD_PADRAO = 10 * 1024 * 1024
LIMITE_UPLOAD_BYTES = int(os.environ.get("NEWPORT_UPLOAD_MAX_BYTES", _LIMITE_UPLOAD_PADRAO))


def limite_upload_bytes() -> int:
    bruto = (os.environ.get("NEWPORT_UPLOAD_MAX_BYTES") or "").strip()
    if not bruto:
        return _LIMITE_UPLOAD_PADRAO
    return int(bruto)
HOSTS_PERMITIDOS_MODO_REAL = frozenset({"127.0.0.1", "localhost", "::1"})
HOSTS_TESTE_AUTOMATIZADO = frozenset({"testclient", "testserver"})
ORIGENS_CORS_DEV = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
)


class ModoExecucao(str, Enum):
    DEMO = "demo"
    REAL = "real"


class ModoExecucaoInvalidoError(ValueError):
    def __init__(self, valor: str) -> None:
        self.valor = valor
        super().__init__(
            f"NEWPORT_MODO inválido: '{valor}'. Use 'demo' ou 'real'."
        )


def modo_execucao() -> ModoExecucao:
    bruto = os.environ.get("NEWPORT_MODO", "demo").strip().lower()
    if bruto == "real":
        return ModoExecucao.REAL
    if bruto == "demo":
        return ModoExecucao.DEMO
    raise ModoExecucaoInvalidoError(bruto)


def bind_host_configurado() -> str:
    env = (os.environ.get("NEWPORT_BIND_HOST") or "").strip()
    if env:
        return env
    # Plataforma (Railway) injeta PORT: escuta em todas as interfaces.
    if modo_hospedado() or (os.environ.get("PORT") or "").strip():
        return "0.0.0.0"
    return "127.0.0.1"


def modo_hospedado() -> bool:
    """Railway / uma instância pública. Liga com NEWPORT_HOSTED=1."""
    bruto = os.environ.get("NEWPORT_HOSTED", "").strip().lower()
    return bruto in {"1", "true", "yes", "sim"}


def origens_cors() -> list[str]:
    """Vite local + origens extras (NEWPORT_CORS_ORIGENS, vírgula)."""
    saida = list(ORIGENS_CORS_DEV)
    extra = os.environ.get("NEWPORT_CORS_ORIGENS") or ""
    for item in extra.split(","):
        origem = item.strip().rstrip("/")
        if origem and origem not in saida:
            saida.append(origem)
    return saida


def exigir_host_local_modo_real() -> None:
    if modo_execucao() != ModoExecucao.REAL:
        return
    if modo_hospedado():
        return
    host = bind_host_configurado()
    if host in HOSTS_PERMITIDOS_MODO_REAL:
        return
    raise RuntimeError(
        "Modo real exige bind em localhost (127.0.0.1). "
        "Não use --host 0.0.0.0 sem NEWPORT_HOSTED=1 e autenticação."
    )


def cliente_eh_local(host: str | None) -> bool:
    if not host:
        return False
    if host in HOSTS_TESTE_AUTOMATIZADO:
        return True
    if host in HOSTS_PERMITIDOS_MODO_REAL:
        return True
    if host.startswith("127."):
        return True
    if host == "::1":
        return True
    return False
