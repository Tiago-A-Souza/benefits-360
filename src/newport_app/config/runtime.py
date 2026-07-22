"""Modo de execução e limites operacionais."""

from __future__ import annotations

import os
from enum import Enum

LIMITE_UPLOAD_BYTES = int(os.environ.get("NEWPORT_UPLOAD_MAX_BYTES", 10 * 1024 * 1024))
HOSTS_PERMITIDOS_MODO_REAL = frozenset({"127.0.0.1", "localhost", "::1"})
HOSTS_TESTE_AUTOMATIZADO = frozenset({"testclient", "testserver"})


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
    return os.environ.get("NEWPORT_BIND_HOST", "127.0.0.1").strip()


def exigir_host_local_modo_real() -> None:
    if modo_execucao() != ModoExecucao.REAL:
        return
    host = bind_host_configurado()
    if host not in HOSTS_PERMITIDOS_MODO_REAL:
        raise RuntimeError(
            "Modo real exige bind em localhost (127.0.0.1). "
            "Não use --host 0.0.0.0 sem autenticação."
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
