"""Usuário do pedido atual (contextvar). Em demo, id fixo 'demo'."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass

from newport_app.config.runtime import ModoExecucao, modo_execucao

USUARIO_DEMO_ID = "demo"

_usuario: ContextVar[UsuarioAtual | None] = ContextVar("benefits_usuario", default=None)


@dataclass(frozen=True)
class UsuarioAtual:
    id: str
    email: str | None = None
    demo: bool = False


def usuario_demo() -> UsuarioAtual:
    return UsuarioAtual(id=USUARIO_DEMO_ID, email=None, demo=True)


def definir_usuario(usuario: UsuarioAtual) -> Token:
    return _usuario.set(usuario)


def reset_usuario(token: Token) -> None:
    _usuario.reset(token)


def usuario_atual() -> UsuarioAtual | None:
    return _usuario.get()


def id_dono() -> str:
    atual = usuario_atual()
    if atual is not None and atual.id:
        return atual.id
    if modo_execucao() == ModoExecucao.DEMO:
        return USUARIO_DEMO_ID
    return ""


def params_visivel() -> tuple[str, int]:
    """Parâmetros do predicado `(usuario_id = ? OR ? = 1)`.

    Em demo o segundo valor é 1: um só operador, lê o banco inteiro
    (rascunhos de teste sem coluna, cópias locais). Fora do demo, 0:
    só as linhas do JWT.
    """
    return (
        id_dono(),
        1 if modo_execucao() == ModoExecucao.DEMO else 0,
    )
