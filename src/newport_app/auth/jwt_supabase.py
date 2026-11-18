"""Valida JWT do Supabase: JWKS (RS256/ES256) com cache, ou HS256 legado."""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

import jwt
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from newport_app.auth.contexto import UsuarioAtual
from newport_app.auth.erros import AutenticacaoError

_JWKS_TTL_S = 3600
_ALGORITMOS_ASSIM = ("RS256", "ES256")


class ValidadorJwtSupabase:
    def __init__(
        self,
        *,
        supabase_url: str,
        jwt_secret: str | None = None,
        jwks: dict[str, Any] | None = None,
        agora=None,
    ) -> None:
        self._url = supabase_url.rstrip("/")
        self._secret = jwt_secret or None
        self._jwks_fixo = jwks
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_em = 0.0
        self._agora = agora or time.time

    def _issuer(self) -> str:
        return f"{self._url}/auth/v1"

    def _jwks_url(self) -> str:
        return f"{self._url}/auth/v1/.well-known/jwks.json"

    def _obter_jwks(self) -> dict[str, Any]:
        if self._jwks_fixo is not None:
            return self._jwks_fixo
        agora = self._agora()
        if self._jwks_cache is not None and (agora - self._jwks_em) < _JWKS_TTL_S:
            return self._jwks_cache
        pedido = urllib.request.Request(self._jwks_url(), method="GET")
        with urllib.request.urlopen(pedido, timeout=5) as resp:  # noqa: S310 — URL do próprio projeto
            dados = json.loads(resp.read().decode("utf-8"))
        self._jwks_cache = dados
        self._jwks_em = agora
        return dados

    def _chave_jwks(self, header: dict[str, Any]):
        jwks = self._obter_jwks()
        kid = header.get("kid")
        for item in jwks.get("keys") or []:
            if kid and item.get("kid") != kid:
                continue
            kty = item.get("kty")
            if kty == "RSA":
                return RSAAlgorithm.from_jwk(item)
            if kty == "EC":
                return ECAlgorithm.from_jwk(item)
        raise AutenticacaoError("Sessão inválida ou expirada. Entre novamente.")

    def validar(self, token: str) -> UsuarioAtual:
        if not token or not token.strip():
            raise AutenticacaoError("Faça login para continuar.")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise AutenticacaoError("Sessão inválida ou expirada. Entre novamente.") from None
        alg = str(header.get("alg") or "")
        opcoes = {"require": ["exp", "sub"], "verify_aud": True}
        try:
            if alg == "HS256":
                if not self._secret:
                    raise AutenticacaoError("Sessão inválida ou expirada. Entre novamente.")
                payload = jwt.decode(
                    token,
                    self._secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                    issuer=self._issuer(),
                    options=opcoes,
                )
            else:
                chave = self._chave_jwks(header)
                payload = jwt.decode(
                    token,
                    chave,
                    algorithms=list(_ALGORITMOS_ASSIM),
                    audience="authenticated",
                    issuer=self._issuer(),
                    options=opcoes,
                )
        except jwt.ExpiredSignatureError:
            raise AutenticacaoError("Sessão inválida ou expirada. Entre novamente.") from None
        except jwt.PyJWTError:
            raise AutenticacaoError("Sessão inválida ou expirada. Entre novamente.") from None
        sub = str(payload.get("sub") or "").strip()
        if not sub:
            raise AutenticacaoError("Sessão inválida ou expirada. Entre novamente.")
        email = payload.get("email")
        return UsuarioAtual(id=sub, email=str(email) if email else None, demo=False)


_validador: ValidadorJwtSupabase | None = None


def configurar_validador(validador: ValidadorJwtSupabase | None) -> None:
    global _validador
    _validador = validador


def obter_validador() -> ValidadorJwtSupabase:
    global _validador
    if _validador is not None:
        return _validador
    import os

    url = (os.environ.get("SUPABASE_URL") or "").strip()
    if not url:
        raise AutenticacaoError("Faça login para continuar.")
    secret = (os.environ.get("SUPABASE_JWT_SECRET") or "").strip() or None
    _validador = ValidadorJwtSupabase(supabase_url=url, jwt_secret=secret)
    return _validador
