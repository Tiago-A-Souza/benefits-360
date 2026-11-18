"""Exige JWT em /api/* exceto GET /api/saude. Em demo, usuário fixo."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from newport_app.auth.contexto import (
    definir_usuario,
    reset_usuario,
    usuario_demo,
)
from newport_app.auth.erros import AutenticacaoError
from newport_app.auth.jwt_supabase import obter_validador
from newport_app.config.runtime import ModoExecucao, modo_execucao

ROTA_PUBLICA = "/api/saude"


def _token_bearer(request: Request) -> str | None:
    bruto = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not bruto.lower().startswith("bearer "):
        return None
    return bruto[7:].strip() or None


def autenticar_request(request: Request):
    if modo_execucao() == ModoExecucao.DEMO:
        return usuario_demo()
    token = _token_bearer(request)
    if not token:
        raise AutenticacaoError("Faça login para continuar.")
    return obter_validador().validar(token)


class AuthSupabaseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path == ROTA_PUBLICA or not path.startswith("/api/"):
            return await call_next(request)
        token_ctx = None
        try:
            usuario = autenticar_request(request)
            token_ctx = definir_usuario(usuario)
            return await call_next(request)
        except AutenticacaoError as exc:
            return JSONResponse({"detail": exc.mensagem}, status_code=401)
        finally:
            if token_ctx is not None:
                reset_usuario(token_ctx)
