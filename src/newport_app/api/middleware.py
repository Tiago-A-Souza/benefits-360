"""Middleware de segurança operacional."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from newport_app.config.runtime import ModoExecucao, cliente_eh_local, modo_execucao


class ModoRealLocalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if modo_execucao() == ModoExecucao.REAL:
            host = request.client.host if request.client else None
            if not cliente_eh_local(host):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Modo real disponível somente em acesso local.",
                    },
                )
        return await call_next(request)
