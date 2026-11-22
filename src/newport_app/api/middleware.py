"""Middleware de segurança operacional."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from newport_app.config.runtime import (
    ModoExecucao,
    cliente_eh_local,
    limite_upload_bytes,
    modo_execucao,
    modo_hospedado,
)


class ModoRealLocalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if modo_execucao() == ModoExecucao.REAL and not modo_hospedado():
            host = request.client.host if request.client else None
            if not cliente_eh_local(host):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Modo real disponível somente em acesso local.",
                    },
                )
        return await call_next(request)


class LimiteUploadMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH"}:
            bruto = request.headers.get("content-length")
            if bruto:
                try:
                    tamanho = int(bruto)
                except ValueError:
                    tamanho = 0
                if tamanho > limite_upload_bytes():
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Arquivo excede o limite permitido para upload."},
                    )
        return await call_next(request)


def _politica_csp() -> str:
    connect = [
        "'self'",
        "http://127.0.0.1:8600",
        "http://localhost:8600",
        "https://*.supabase.co",
        "wss://*.supabase.co",
    ]
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    if url:
        connect.append(url)
        if url.startswith("https://"):
            connect.append("wss://" + url[len("https://") :])
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        f"connect-src {' '.join(connect)}; "
        "frame-src 'self' http://127.0.0.1:8600 http://localhost:8600; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )


class CabecalhosSegurancaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault("Content-Security-Policy", _politica_csp())
        if modo_hospedado():
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
