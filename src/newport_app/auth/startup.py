"""Recusa subir sem o essencial quando não é demo."""

from __future__ import annotations

import os

from newport_app.config.runtime import (
    ModoExecucao,
    exigir_host_local_modo_real,
    modo_execucao,
    modo_hospedado,
)


class AuthNaoConfiguradaError(RuntimeError):
    pass


class HospedagemNaoConfiguradaError(AuthNaoConfiguradaError):
    pass


def exigir_auth_configurada() -> None:
    hosted = modo_hospedado()
    modo = modo_execucao()
    if hosted and modo == ModoExecucao.DEMO:
        raise HospedagemNaoConfiguradaError(
            "NEWPORT_HOSTED=1 não permite NEWPORT_MODO=demo (um único usuário "
            "aberto, sem login). Use NEWPORT_MODO=real e SUPABASE_URL."
        )
    if modo == ModoExecucao.DEMO:
        return
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    if not url:
        raise AuthNaoConfiguradaError(
            "NEWPORT_MODO=real e SUPABASE_URL não está definida. "
            "O backend não sobe sem autenticação. Defina SUPABASE_URL "
            "(o mesmo valor de VITE_SUPABASE_URL). Nunca use a chave "
            "service_role."
        )
    if hosted:
        volume = (
            os.environ.get("NEWPORT_VOLUME_DIR")
            or os.environ.get("NEWPORT_PRIVATE_RUNTIME")
            or ""
        ).strip()
        if not volume:
            raise HospedagemNaoConfiguradaError(
                "NEWPORT_HOSTED=1 exige NEWPORT_VOLUME_DIR (ou "
                "NEWPORT_PRIVATE_RUNTIME) apontando para o volume persistente. "
                "Sem isso os bancos SQLite se perdem a cada deploy."
            )
    exigir_host_local_modo_real()
