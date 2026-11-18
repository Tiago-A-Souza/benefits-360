"""Recusa subir sem SUPABASE_URL quando não é demo."""

from __future__ import annotations

import os

from newport_app.config.runtime import ModoExecucao, modo_execucao


class AuthNaoConfiguradaError(RuntimeError):
    pass


def exigir_auth_configurada() -> None:
    if modo_execucao() == ModoExecucao.DEMO:
        return
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    if not url:
        raise AuthNaoConfiguradaError(
            "NEWPORT_MODO não é demo e SUPABASE_URL não está definida. "
            "O backend não sobe sem autenticação. Defina SUPABASE_URL "
            "(o mesmo valor de VITE_SUPABASE_URL) em .env.local."
        )
